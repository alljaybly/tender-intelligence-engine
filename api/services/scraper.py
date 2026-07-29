# scraper.py
import time
import logging
import os
import shutil
import re
import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import TimeoutException, StaleElementReferenceException, WebDriverException
from webdriver_manager.chrome import ChromeDriverManager
import traceback

from api.services.ai_engine.parser import extract_text_from_pdf
from api.services.ai_engine.summarizer import summarize_text
from api.services.ai_engine.scorer import score_tender

# ---------------------------------------------------------------------------
# Directory setup
# ---------------------------------------------------------------------------
BASE_DIR = os.getcwd()
LOGS_DIR = os.path.join(BASE_DIR, 'logs')
DOWNLOADS_DIR = os.path.join(BASE_DIR, 'downloads')
DATA_DIR = os.path.join(BASE_DIR, 'data')
TEMP_DOWNLOAD_DIR = os.path.join(BASE_DIR, 'temp_downloads')

for directory in [LOGS_DIR, DOWNLOADS_DIR, DATA_DIR, TEMP_DOWNLOAD_DIR]:
    if not os.path.exists(directory):
        os.makedirs(directory)

# ---------------------------------------------------------------------------
# Logging — use a named logger so basicConfig from other modules doesn't
# clobber our format.
# ---------------------------------------------------------------------------
logger = logging.getLogger("etenders_scraper")
if not logger.handlers:
    _fh = logging.FileHandler(os.path.join(LOGS_DIR, 'scraper.log'))
    _sh = logging.StreamHandler()
    _fmt = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    _fh.setFormatter(_fmt)
    _sh.setFormatter(_fmt)
    logger.addHandler(_fh)
    logger.addHandler(_sh)
    logger.setLevel(logging.INFO)


# ---------------------------------------------------------------------------
# Custom WebDriverWait condition: table has at least N rows with non-empty
# text in a data cell.
#
# NOTE: cells[0] on the eTenders DataTable is always the expand/collapse
# icon column (<td class="details-control"></td>) which has NO text.
# We must check cells[1] (Category) or cells[2] (Title Description) instead.
# ---------------------------------------------------------------------------
class TableHasPopulatedRows:
    """
    Wait condition that returns the list of <tr> elements once at least
    `min_rows` rows have non-empty text in a data column.
    Checks cell[1] (Category) and cell[2] (Title) — NOT cell[0] which is
    an always-empty icon column.
    """
    def __init__(self, css_selector: str, min_rows: int = 1):
        self.css = css_selector
        self.min_rows = min_rows

    def __call__(self, driver):
        rows = driver.find_elements(By.CSS_SELECTOR, self.css)
        populated = []
        for row in rows:
            try:
                cells = row.find_elements(By.TAG_NAME, "td")
                # cells[0] is an icon column (always empty text).
                # Check cells[1] (Category) or cells[2] (Title) for real data.
                if len(cells) >= 3 and (cells[1].text.strip() or cells[2].text.strip()):
                    populated.append(row)
            except StaleElementReferenceException:
                continue
        return populated if len(populated) >= self.min_rows else False


class ETendersScraper:
    # How long (seconds) to wait for page/AJAX operations.
    PAGE_LOAD_TIMEOUT = 180   # Chrome page load hard limit
    ELEMENT_WAIT     = 90    # WebDriverWait for table population
    EXPAND_WAIT      = 10    # seconds after clicking expand button
    PAGINATION_WAIT  = 30    # seconds after clicking next-page

    def __init__(self):
        logger.info("[INIT] Initializing ETendersScraper...")
        self.base_dir = BASE_DIR
        self.temp_download_dir = TEMP_DOWNLOAD_DIR
        self.final_download_dir = DOWNLOADS_DIR
        self.data_dir = DATA_DIR

        # Clean temp directory on startup
        self.clean_temp_dir()

        # ------------------------------------------------------------------
        # Chrome options
        # ------------------------------------------------------------------
        chrome_options = Options()
        chrome_options.add_argument('--start-maximized')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        # Disable GPU rendering (helps in headless/server environments)
        chrome_options.add_argument('--disable-gpu')
        # Increase connection timeout inside Chrome itself
        chrome_options.add_argument('--dns-prefetch-disable')

        # --page-load-strategy=eager returns as soon as DOM is interactive,
        # without waiting for images, fonts, or AJAX to finish loading.
        # This avoids the Selenium client ReadTimeoutError (~120s socket timeout)
        # on slow government sites. The actual tender AJAX data is waited for
        # separately by the _wait_for_populated_table() method.
        chrome_options.add_argument('--blink-settings=imagesEnabled=false')
        chrome_options.page_load_strategy = 'eager'

        chrome_options.add_experimental_option('prefs', {
            'download.default_directory': self.temp_download_dir,
            'download.prompt_for_download': False,
            'download.directory_upgrade': True,
            'safebrowsing.enabled': True,
            'plugins.always_open_pdf_externally': True
        })

        # ------------------------------------------------------------------
        # ChromeDriverManager: tell webdriver_manager to use a longer HTTP
        # timeout and prefer the locally cached driver to avoid ReadTimeoutError
        # on the version-check network call.
        # WDM_LOCAL=1  → skip the remote version check entirely if a cached
        #                 driver already exists.
        # ------------------------------------------------------------------
        os.environ.setdefault("WDM_LOCAL", "1")
        os.environ.setdefault("WDM_LOG_LEVEL", "0")   # suppress noisy wdm logs

        logger.info("[INIT] Installing/locating ChromeDriver...")
        try:
            service = Service(ChromeDriverManager().install())
        except Exception as e:
            logger.error("[INIT] ChromeDriverManager failed: %s — retrying without cache check", e)
            # Force a fresh download on retry
            os.environ["WDM_LOCAL"] = "0"
            service = Service(ChromeDriverManager().install())

        self.driver = webdriver.Chrome(service=service, options=chrome_options)

        # Increase the Selenium socket-level command timeout from the default
        # ~120s to match our PAGE_LOAD_TIMEOUT, preventing ReadTimeoutError on
        # the HTTP connection between Python and ChromeDriver.
        # Use the newer client_config API if available, fall back to set_timeout.
        try:
            from selenium.webdriver.remote.client_config import ClientConfig
            self.driver.command_executor.set_timeout(self.PAGE_LOAD_TIMEOUT + 30)
        except ImportError:
            self.driver.command_executor.set_timeout(self.PAGE_LOAD_TIMEOUT + 30)

        # Hard page-load timeout so Chrome never hangs indefinitely
        self.driver.set_page_load_timeout(self.PAGE_LOAD_TIMEOUT)

        # WebDriverWait used for element-level waits
        self.wait = WebDriverWait(
            self.driver,
            self.ELEMENT_WAIT,
            poll_frequency=2,
            ignored_exceptions=[StaleElementReferenceException],
        )

        logger.info("[INIT] Chrome driver ready.")

        # ------------------------------------------------------------------
        # Keywords
        # ------------------------------------------------------------------
        self.keywords = {
            'CONSTRUCTION': [
                'build', 'building', 'construction', 'construct', 'civil',
                'civil works', 'maintenance', 'repair', 'repairs', 'renovation',
                'upgrade', 'upgrading', 'facility', 'facilities', 'infrastructure',
                'road', 'roads', 'stormwater', 'water', 'sewer', 'pipeline',
                'plumbing', 'electrical', 'painting', 'roof', 'roofing', 'tiling',
                'carpentry', 'flooring', 'concrete', 'brick', 'paving', 'contractor'
            ],
            'CLEANING': [
                'clean', 'cleaner', 'hygiene', 'sanitize', 'janitor', 'housekeep',
                'waste', 'refuse', 'garbage', 'rubbish', 'litter', 'recycle',
                'pest', 'fumigate', 'window wash', 'pressure wash',
                'carpet clean', 'deep clean'
            ],
            'SUPPLY': [
                'supply', 'deliver', 'provide', 'procure', 'purchase', 'material',
                'equipment', 'tool', 'machinery', 'cement', 'brick', 'pipe',
                'cable', 'fitting', 'steel', 'timber', 'wood', 'glass'
            ]
        }

        self.all_keywords = set()
        for cat_list in self.keywords.values():
            self.all_keywords.update(cat_list)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def clean_temp_dir(self):
        """Remove all files from temp download directory."""
        for filename in os.listdir(self.temp_download_dir):
            file_path = os.path.join(self.temp_download_dir, filename)
            try:
                if os.path.isfile(file_path) or os.path.islink(file_path):
                    os.unlink(file_path)
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path)
            except Exception as e:
                logger.error('[CLEANUP] Failed to delete %s: %s', file_path, e)

    def remove_overlays(self):
        """Remove modal backdrops and specific popups."""
        try:
            self.driver.execute_script("""
                document.querySelectorAll('.modal-backdrop').forEach(b => b.remove());
                document.body.classList.remove('modal-open');
                var popup = document.getElementById('educationalPopup');
                if (popup) { popup.remove(); }
            """)
        except Exception as e:
            logger.warning("[OVERLAY] Error removing overlays: %s", e)

    def sanitize_filename(self, filename):
        """Sanitize string to be used as filename."""
        return re.sub(r'[<>:"/\\|?*]', '_', filename).strip()

    def wait_for_download(self, timeout=60):
        """Wait for a file to appear in the temp folder and return its path."""
        end_time = time.time() + timeout
        while time.time() < end_time:
            files = os.listdir(self.temp_download_dir)
            completed_files = [
                f for f in files
                if not f.endswith('.crdownload') and not f.endswith('.tmp')
            ]
            if completed_files:
                latest_file = max(
                    [os.path.join(self.temp_download_dir, f) for f in completed_files],
                    key=os.path.getmtime
                )
                time.sleep(1)  # ensure file handle is released
                return latest_file
            time.sleep(1)
        return None

    def check_relevance(self, text):
        """Return True if any keyword appears in text."""
        text_lower = text.lower()
        return any(k.lower() in text_lower for k in self.all_keywords)

    def get_tender_category(self, text):
        """Determine broad category based on keywords."""
        text_lower = text.lower()
        found_cats = [
            cat for cat, kws in self.keywords.items()
            if any(k in text_lower for k in kws)
        ]
        return "_".join(found_cats) if found_cats else "General"

    def _debug_dom_structure(self):
        """Log every table, iframe, and key structural elements found on the page.
        This is a diagnostic method — remove after fixing selectors.
        """
        logger.info("========== DOM DIAGNOSTIC ==========")

        # ── Check all <table> elements ──
        tables = self.driver.find_elements(By.CSS_SELECTOR, "table")
        logger.info("[DOM] Found %d <table> elements.", len(tables))
        for idx, tbl in enumerate(tables):
            try:
                table_id = tbl.get_attribute("id") or "(none)"
                table_class = tbl.get_attribute("class") or "(none)"
                rows = tbl.find_elements(By.CSS_SELECTOR, "tbody tr")
                row_count = len(rows)
                logger.info("[DOM] Table #%d: id=%s class=%s tbody_rows=%d",
                            idx, table_id, table_class, row_count)

                # Dump first 5 rows
                for ri, row in enumerate(rows[:5]):
                    cells = row.find_elements(By.TAG_NAME, "td")
                    cell_text = [c.text.strip()[:80] for c in cells]
                    logger.info("[DOM]   Row %d: cells=%d text=%s",
                                ri, len(cells), cell_text[:6])

                # Also dump any thead for column headers
                thead = tbl.find_elements(By.CSS_SELECTOR, "thead tr th")
                if thead:
                    headers = [th.text.strip()[:40] for th in thead]
                    logger.info("[DOM]   headers=%s", headers)
            except Exception as e:
                logger.warning("[DOM] Error inspecting table #%d: %s", idx, e)

        # ── Check for <iframe> elements ──
        iframes = self.driver.find_elements(By.TAG_NAME, "iframe")
        logger.info("[DOM] Found %d <iframe> elements.", len(iframes))
        for idx, ifr in enumerate(iframes):
            try:
                src = ifr.get_attribute("src") or "(none)"
                ifr_id = ifr.get_attribute("id") or "(none)"
                logger.info("[DOM] iframe #%d: id=%s src=%s", idx, ifr_id, src)
            except Exception as e:
                logger.warning("[DOM] Error inspecting iframe #%d: %s", idx, e)

        # ── Check for shadow roots  ──
        shadow_hosts = self.driver.execute_script("""
            return Array.from(document.querySelectorAll('*')).filter(
                el => el.shadowRoot
            ).map(el => el.tagName + (el.id ? '#' + el.id : ''));
        """)
        logger.info("[DOM] Elements with shadowRoot: %s", shadow_hosts or "none")

        # ── Check for DataTable / AJAX state ──
        dt_info = self.driver.execute_script("""
            var info = {};
            var dt = $?.fn?.dataTable ? 'jQuery DataTable present' : 'no jQuery DataTable';
            info['datatable'] = dt;
            var tables = document.querySelectorAll('table');
            var tableIds = Array.from(tables).map(t => t.id || '(no id)');
            info['table_ids'] = tableIds;
            // Check for any hidden containers that might hold data
            var hiddenContainers = Array.from(document.querySelectorAll('div[style*="display:none"], div[style*="display: none"], div.hidden'));
            info['hidden_divs'] = hiddenContainers.length;
            return JSON.stringify(info);
        """)
        logger.info("[DOM] JS info: %s", dt_info)

        # ── Page source snippet for first table with DataTable ──
        logger.info("[DOM] Page title: %s", self.driver.title)
        logger.info("[DOM] URL: %s", self.driver.current_url)

        # Dump the outer HTML of the first few tables for exact structure
        for idx, tbl in enumerate(tables[:2]):
            try:
                html = tbl.get_attribute("outerHTML")
                logger.info("[DOM] Table #%d outerHTML (first 3000 chars):\n%s",
                            idx, html[:3000])
            except Exception as e:
                logger.warning("[DOM] Could not get outerHTML for table #%d: %s", idx, e)

        logger.info("========== END DOM DIAGNOSTIC ==========")

    def _wait_for_populated_table(self, page_num: int):
        """
        Wait until the table has at least 1 row with non-empty text in the
        Category (col 1) or Title (col 2) cells.
        Raises TimeoutException if the table never populates within ELEMENT_WAIT.
        """
        logger.info("[PAGE %d] Waiting for table to populate with data...", page_num)
        try:
            populated_rows = WebDriverWait(
                self.driver,
                self.ELEMENT_WAIT,
                poll_frequency=2,
                ignored_exceptions=[StaleElementReferenceException],
            ).until(TableHasPopulatedRows("table tbody tr", min_rows=1))
            logger.info("[PAGE %d] Table populated — %d rows detected.", page_num, len(populated_rows))
            return populated_rows
        except TimeoutException:
            logger.error(
                "[PAGE %d] Timed out waiting for populated table data after %ds.",
                page_num, self.ELEMENT_WAIT
            )
            raise

    # ------------------------------------------------------------------
    # Main scraping logic
    # ------------------------------------------------------------------

    def process_tenders(self):
        tenders_data = []

        try:
            logger.info("[NAV] Navigating to eTenders opportunities page...")
            try:
                self.driver.get("https://www.etenders.gov.za/Home/opportunities?id=1")
            except TimeoutException:
                # Page load timed out but the DOM may still be usable (common on slow gov sites)
                logger.warning(
                    "[NAV] Page load timed out after %ds — attempting to continue with partial DOM.",
                    self.PAGE_LOAD_TIMEOUT
                )

            logger.info("[NAV] Page navigation complete. Running DOM diagnostic...")

            # ── DIAGNOSTIC: dump all tables, iframes, and shadow DOM ──
            self._debug_dom_structure()
            # ───────────────────────────────────────────────────────────

            max_pages = 5
            page_num = 1

            while page_num <= max_pages:
                logger.info("[PAGE %d] ── Starting page processing ──", page_num)

                # ── Wait for table to have real data (not just DOM presence) ──
                try:
                    self.remove_overlays()
                    populated_rows = self._wait_for_populated_table(page_num)
                except TimeoutException:
                    logger.error("[PAGE %d] Table never populated — stopping pagination.", page_num)
                    break

                logger.info("[PAGE %d] Found %d populated rows to process.", page_num, len(populated_rows))

                i = 0
                while i < len(populated_rows):
                    try:
                        # Re-fetch rows each iteration to avoid stale references
                        try:
                            current_rows = self._wait_for_populated_table(page_num)
                        except TimeoutException:
                            logger.warning("[PAGE %d] Row re-fetch timed out at index %d — stopping page.", page_num, i)
                            break

                        if i >= len(current_rows):
                            logger.info("[PAGE %d] Row index %d exceeds current row count %d — done with page.", page_num, i, len(current_rows))
                            break

                        row = current_rows[i]

                        # ── Extract cell data ──
                        # Column layout from DOM diagnostic (table#tendeList):
                        #   [0] expand icon (always empty)
                        #   [1] Category
                        #   [2] Title (tender description)
                        #   [3] eSubmission icon
                        #   [4] Advertised date
                        #   [5] Closing
                        #   [6] bookmark icons
                        cells = row.find_elements(By.TAG_NAME, "td")

                        if len(cells) < 6:
                            logger.debug("[PAGE %d] Row %d has only %d cells — skipping.", page_num, i, len(cells))
                            i += 1  # CRITICAL: must increment to avoid infinite loop
                            continue

                        tender_ref    = ""   # no separate tender-ref column on this page — use title as key
                        category_text = cells[1].text.strip()
                        title         = cells[2].text.strip()
                        closing_date  = cells[5].text.strip()

                        logger.info(
                            "[PAGE %d] Row %d — cat=%r title=%r closing=%r",
                            page_num, i, category_text, title[:60], closing_date
                        )

                        full_text = f"{title} {category_text}"

                        # ── Relevance filter ──
                        if not self.check_relevance(full_text):
                            logger.info("[PAGE %d] Row %d — SKIPPED (not relevant): %r", page_num, i, tender_ref)
                            i += 1
                            continue

                        logger.info("[PAGE %d] Row %d — RELEVANT tender: %r", page_num, i, tender_ref)

                        tender_cat = self.get_tender_category(full_text)

                        # ── Expand row ──
                        try:
                            expand_btn = row.find_element(By.CSS_SELECTOR, "td.details-control")
                            self.driver.execute_script("arguments[0].scrollIntoView(true);", expand_btn)
                            time.sleep(0.5)
                            expand_btn.click()
                            logger.info("[PAGE %d] Row %d — expand clicked, waiting %ds for child row...", page_num, i, self.EXPAND_WAIT)
                            time.sleep(self.EXPAND_WAIT)
                        except Exception as e:
                            logger.warning("[PAGE %d] Row %d — could not click expand: %s", page_num, i, e)
                            i += 1
                            continue

                        # ── Find expanded child row ──
                        expanded_row = None
                        try:
                            expanded_row = row.find_element(By.XPATH, "following-sibling::tr[@class='child']")
                            logger.info("[PAGE %d] Row %d — child row found (class='child').", page_num, i)
                        except Exception:
                            try:
                                expanded_row = row.find_element(By.XPATH, "following-sibling::tr[1]")
                                logger.info("[PAGE %d] Row %d — child row found (first sibling fallback).", page_num, i)
                            except Exception as e:
                                logger.warning("[PAGE %d] Row %d — no expanded row found: %s", page_num, i, e)
                                i += 1
                                continue

                        # ── Download PDFs ──
                        pdf_links = expanded_row.find_elements(
                            By.CSS_SELECTOR,
                            "a[href$='.pdf'], a[href*='Download'], a[href*='.PDF']"
                        )
                        logger.info("[PAGE %d] Row %d — found %d PDF link(s).", page_num, i, len(pdf_links))

                        document_paths = []

                        folder_name = self.sanitize_filename(f"{tender_ref}_{tender_cat}") if tender_ref else \
                                      self.sanitize_filename(f"{title[:20]}_{tender_cat}")
                        tender_download_path = os.path.join(self.final_download_dir, folder_name)

                        if pdf_links:
                            if not os.path.exists(tender_download_path):
                                os.makedirs(tender_download_path)

                            for link in pdf_links:
                                try:
                                    pdf_url = link.get_attribute('href')
                                    if not pdf_url or 'mailto:' in pdf_url:
                                        continue

                                    self.clean_temp_dir()
                                    logger.info("[DOWNLOAD] Downloading: %s", pdf_url)

                                    self.driver.execute_script("arguments[0].scrollIntoView(true);", link)
                                    time.sleep(1)
                                    link.click()

                                    downloaded_file = self.wait_for_download(timeout=60)

                                    if downloaded_file:
                                        filename = os.path.basename(downloaded_file)
                                        final_path = os.path.join(tender_download_path, filename)

                                        if os.path.exists(final_path):
                                            base, ext = os.path.splitext(filename)
                                            final_path = os.path.join(
                                                tender_download_path,
                                                f"{base}_{int(time.time())}{ext}"
                                            )

                                        shutil.move(downloaded_file, final_path)
                                        document_paths.append(final_path)
                                        logger.info("[DOWNLOAD] Saved: %s", final_path)

                                        # ── AI processing ──
                                        try:
                                            text = extract_text_from_pdf(final_path)
                                            summary = summarize_text(text)
                                            score = score_tender(text)
                                            logger.info("[AI] %s — summary=%s score=%s", filename, summary, score)
                                        except Exception as ai_error:
                                            logger.error("[AI] Processing failed for %s: %s", final_path, ai_error)
                                    else:
                                        logger.error("[DOWNLOAD] Timed out waiting for: %s", pdf_url)

                                except Exception as e:
                                    logger.error("[DOWNLOAD] Failed for link: %s", e)

                        # ── Collapse row ──
                        try:
                            expand_btn.click()
                            time.sleep(1)
                        except Exception:
                            pass

                        # ── Record tender ──
                        tenders_data.append({
                            'tender_ref':       tender_ref,
                            'title':            title,
                            'category':         category_text,
                            'closing_date':     closing_date,
                            'num_documents':    len(document_paths),
                            'downloaded_paths': "; ".join(document_paths)
                        })
                        logger.info(
                            "[PAGE %d] Row %d — recorded tender %r (%d docs).",
                            page_num, i, tender_ref, len(document_paths)
                        )

                        i += 1

                    except StaleElementReferenceException:
                        logger.warning("[PAGE %d] Row %d — stale element, re-fetching...", page_num, i)
                        # Don't increment i — retry the same index with fresh rows
                        time.sleep(2)
                        continue
                    except Exception as e:
                        logger.error("[PAGE %d] Row %d — unexpected error: %s", page_num, i, e)
                        traceback.print_exc()
                        i += 1
                        continue

                logger.info(
                    "[PAGE %d] ── Page complete. Tenders collected so far: %d ──",
                    page_num, len(tenders_data)
                )

                # ── Pagination ──
                if page_num >= max_pages:
                    logger.info("[PAGINATION] Max pages (%d) reached — stopping.", max_pages)
                    break

                try:
                    next_btn = self.driver.find_element(
                        By.CSS_SELECTOR, "a.paginate_button.next:not(.disabled)"
                    )
                    logger.info("[PAGINATION] Clicking next page button...")
                    self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                    time.sleep(1)
                    next_btn.click()

                    # Wait for the table to go stale (old data disappears) then repopulate
                    logger.info("[PAGINATION] Waiting up to %ds for next page data...", self.PAGINATION_WAIT)
                    time.sleep(3)  # brief pause for AJAX to start
                    try:
                        # Wait for table to repopulate with fresh data
                        WebDriverWait(self.driver, self.PAGINATION_WAIT, poll_frequency=2).until(
                            TableHasPopulatedRows("table tbody tr", min_rows=1)
                        )
                        logger.info("[PAGINATION] Next page data loaded.")
                    except TimeoutException:
                        logger.warning(
                            "[PAGINATION] Next page data did not appear within %ds — stopping.",
                            self.PAGINATION_WAIT
                        )
                        break

                    page_num += 1

                except Exception:
                    logger.info("[PAGINATION] No next button found or pagination ended.")
                    break

            # ── Save CSV ──
            if tenders_data:
                df = pd.DataFrame(tenders_data)
                csv_path = os.path.join(self.data_dir, 'relevant_tenders_summary.csv')
                df.to_csv(csv_path, index=False)
                logger.info("[COMPLETE] Saved %d tenders to %s", len(tenders_data), csv_path)
            else:
                logger.info("[COMPLETE] No relevant tenders found.")

        except WebDriverException as e:
            logger.error("[FATAL] WebDriver error: %s", e)
            traceback.print_exc()
        except Exception as e:
            logger.error("[FATAL] Unexpected error: %s", e)
            traceback.print_exc()
        finally:
            # driver.quit() always runs — but only AFTER all scraping is done
            # (the finally block is reached only when the try/except above exits)
            logger.info("[SHUTDOWN] Scraping finished. Quitting Chrome driver...")
            try:
                self.driver.quit()
                logger.info("[SHUTDOWN] Chrome driver quit successfully.")
            except Exception as e:
                logger.warning("[SHUTDOWN] Error quitting driver: %s", e)

        logger.info("[RESULT] Returning %d tenders.", len(tenders_data))
        return tenders_data


def scrape_tenders():
    scraper = ETendersScraper()
    return scraper.process_tenders()


if __name__ == "__main__":
    scraper = ETendersScraper()
    scraper.process_tenders()
