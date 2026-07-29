/**
 * BackToTop — A floating button that appears in the bottom-right corner
 * once the user scrolls down past a threshold (400px). Clicking it
 * smoothly scrolls back to the top of the page.
 *
 * Renders nothing until the user has scrolled enough, so there is no
 * layout impact on initial page load.
 */
import { useState, useEffect } from 'react';
import { ArrowUp } from 'lucide-react';

const SCROLL_THRESHOLD = 400;

export function BackToTop() {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    function onScroll() {
      setVisible(window.scrollY > SCROLL_THRESHOLD);
    }

    window.addEventListener('scroll', onScroll, { passive: true });
    onScroll(); // Check initial position

    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  function scrollToTop() {
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  if (!visible) return null;

  return (
    <button
      onClick={scrollToTop}
      aria-label="Back to top"
      className="fixed bottom-6 right-6 z-50 flex h-12 w-12 items-center justify-center rounded-full bg-blue-600 text-white shadow-lg transition-all hover:bg-blue-700 hover:shadow-xl active:scale-95 animate-fade-in"
    >
      <ArrowUp className="h-5 w-5" />
    </button>
  );
}

export default BackToTop;