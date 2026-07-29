/**
 * UploadCard — Tender document upload component.
 *
 * Supports:
 * - PDF, DOCX, TXT file upload
 * - File validation (type, size)
 * - Real multipart/form-data upload via XHR with progress tracking
 * - Duplicate warnings from backend
 * - Disabled state during upload
 * - Loading/error states
 */
import { useState, useRef, type ChangeEvent } from 'react';
import { Upload, FileText, X, AlertTriangle, CheckCircle, Loader2 } from 'lucide-react';
import { uploadTender } from '../services/process';
import {
  ALLOWED_EXTENSIONS,
  MAX_FILE_SIZE,
} from '../types/process';
import type { ProcessUploadResponse } from '../types/process';

interface UploadCardProps {
  /** Called when upload succeeds with the response data. */
  onUploadSuccess: (response: ProcessUploadResponse) => void;
}

export default function UploadCard({ onUploadSuccess }: UploadCardProps) {
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  function validateFile(selectedFile: File): string | null {
    const ext = '.' + selectedFile.name.split('.').pop()?.toLowerCase();
    if (!ALLOWED_EXTENSIONS.includes(ext as typeof ALLOWED_EXTENSIONS[number])) {
      return `Unsupported file type "${ext}". Allowed: PDF, DOCX, TXT.`;
    }
    if (selectedFile.size > MAX_FILE_SIZE) {
      return `File too large (${(selectedFile.size / (1024 * 1024)).toFixed(1)} MB). Maximum size is 50 MB.`;
    }
    if (selectedFile.size === 0) {
      return 'File is empty. Please select a non-empty file.';
    }
    return null;
  }

  function handleFileChange(e: ChangeEvent<HTMLInputElement>) {
    const selectedFile = e.target.files?.[0] || null;
    setFile(selectedFile);
    setError(null);
    setSuccessMessage(null);
    setProgress(0);

    if (selectedFile) {
      const validationError = validateFile(selectedFile);
      if (validationError) {
        setError(validationError);
        setFile(null);
        if (fileInputRef.current) {
          fileInputRef.current.value = '';
        }
      }
    }
  }

  async function handleUpload() {
    if (!file) {
      setError('Please select a file first.');
      return;
    }

    const validationError = validateFile(file);
    if (validationError) {
      setError(validationError);
      return;
    }

    setUploading(true);
    setError(null);
    setSuccessMessage(null);
    setProgress(0);

    try {
      const response = await uploadTender(file, (percent: number) => {
        setProgress(percent);
      });

      setProgress(100);
      setSuccessMessage(`${file.name} uploaded successfully!`);
      setFile(null);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
      onUploadSuccess(response);
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : 'Upload failed. Please try again.';
      setError(message);
    } finally {
      setUploading(false);
    }
  }

  function handleCancel() {
    setFile(null);
    setError(null);
    setSuccessMessage(null);
    setProgress(0);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  }

  return (
    <div className="rounded-xl border border-gray-200 bg-white shadow-sm">
      <div className="px-5 py-4 border-b border-gray-200">
        <div className="flex items-center gap-2">
          <div className="h-8 w-8 rounded-lg bg-blue-50 flex items-center justify-center">
            <Upload className="h-4 w-4 text-blue-600" />
          </div>
          <div>
            <h2 className="text-sm font-semibold text-gray-900">Upload Tender</h2>
            <p className="text-xs text-gray-500">
              PDF, DOCX, or TXT (max 50 MB)
            </p>
          </div>
        </div>
      </div>

      <div className="px-5 py-4 space-y-4">
        {/* Cold start note for free Render tier */}
        <div className="flex items-start gap-2.5 bg-amber-50 border border-amber-200 rounded-lg px-3.5 py-2.5">
          <svg className="h-4 w-4 text-amber-500 flex-shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z" />
          </svg>
          <p className="text-xs text-amber-700 leading-relaxed">
            <span className="font-semibold">Free Render cold start:</span> First request may take <span className="font-semibold">~30s</span> while the backend wakes up. Processing then runs normally.
          </p>
        </div>

        {/* File input */}
        <div>
          <input
            ref={fileInputRef}
            id="tender-file-upload"
            type="file"
            accept=".pdf,.docx,.txt,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/plain"
            onChange={handleFileChange}
            disabled={uploading}
            className="block w-full text-sm text-gray-500
              file:mr-3 file:py-2 file:px-4
              file:rounded-lg file:border-0
              file:text-sm file:font-semibold
              file:bg-blue-50 file:text-blue-700
              hover:file:bg-blue-100
              disabled:opacity-50 disabled:cursor-not-allowed
              cursor-pointer transition-colors"
          />
        </div>

        {/* Selected file info */}
        {file && !uploading && !error && (
          <div className="flex items-center justify-between bg-gray-50 rounded-lg px-3 py-2.5 border border-gray-100">
            <div className="flex items-center gap-2.5 min-w-0">
              <FileText className="h-4 w-4 text-blue-500 flex-shrink-0" />
              <span className="text-sm text-gray-700 truncate font-medium">
                {file.name}
              </span>
              <span className="text-xs text-gray-400 flex-shrink-0 tabular-nums">
                ({(file.size / 1024).toFixed(1)} KB)
              </span>
            </div>
            <button
              onClick={handleCancel}
              className="p-1 rounded-md hover:bg-gray-200 transition-colors flex-shrink-0"
              aria-label="Remove file"
            >
              <X className="h-4 w-4 text-gray-400" />
            </button>
          </div>
        )}

        {/* Upload progress bar */}
        {uploading && (
          <div>
            <div className="flex items-center justify-between text-sm text-gray-600 mb-1.5">
              <div className="flex items-center gap-2">
                <Loader2 className="h-4 w-4 animate-spin text-blue-500" />
                <span>Uploading...</span>
              </div>
              <span className="font-medium tabular-nums">{progress}%</span>
            </div>
            <div className="w-full bg-gray-100 rounded-full h-2 overflow-hidden">
              <div
                className="bg-blue-600 h-full rounded-full transition-all duration-300"
                style={{ width: `${progress}%` }}
              />
            </div>
          </div>
        )}

        {/* Error message */}
        {error && (
          <div className="flex items-start gap-2.5 bg-red-50 border border-red-200 rounded-lg px-3.5 py-3">
            <AlertTriangle className="h-4 w-4 text-red-500 flex-shrink-0 mt-0.5" />
            <p className="text-sm text-red-700">{error}</p>
          </div>
        )}

        {/* Success message */}
        {successMessage && (
          <div className="flex items-start gap-2.5 bg-emerald-50 border border-emerald-200 rounded-lg px-3.5 py-3">
            <CheckCircle className="h-4 w-4 text-emerald-500 flex-shrink-0 mt-0.5" />
            <p className="text-sm text-emerald-700">{successMessage}</p>
          </div>
        )}

        {/* Action buttons */}
        <div className="flex gap-3">
          <button
            onClick={handleUpload}
            disabled={!file || uploading}
            className="inline-flex items-center gap-1.5 px-4 py-2.5 border border-transparent
              text-sm font-semibold rounded-lg shadow-sm text-white
              bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2
              focus:ring-offset-2 focus:ring-blue-500
              disabled:opacity-50 disabled:cursor-not-allowed
              transition-colors"
          >
            {uploading ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Uploading...
              </>
            ) : (
              <>
                <Upload className="h-4 w-4" />
                Upload & Process
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}