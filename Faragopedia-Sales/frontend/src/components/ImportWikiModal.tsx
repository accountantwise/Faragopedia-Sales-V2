import React, { useState, useRef, useEffect } from 'react'
import { X, Upload, FileText, AlertTriangle, CheckCircle, Loader2 } from 'lucide-react'
import { API_BASE } from '../config'

interface Props {
  folder: string
  onClose: () => void
  onImported: () => void
}

type ConflictResolution = 'overwrite' | 'skip' | { rename: string }

interface QueuedFile {
  file: File
  status: 'ready' | 'conflict' | 'imported' | 'error'
  resolution?: ConflictResolution
  renameValue?: string
  errorMessage?: string
}

export default function ImportWikiModal({ folder, onClose, onImported }: Props) {
  const [queuedFiles, setQueuedFiles] = useState<QueuedFile[]>([])
  const [isDragging, setIsDragging] = useState(false)
  const [skippedCount, setSkippedCount] = useState(0)
  const [importing, setImporting] = useState(false)
  const [existingPages, setExistingPages] = useState<Set<string>>(new Set())
  const fileInputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    fetch(`${API_BASE}/pages`)
      .then(r => r.json())
      .then((data: Record<string, string[]>) => {
        const pages = data[folder] || []
        setExistingPages(new Set(pages.map(p => p.split('/').pop()!)))
      })
      .catch(() => {})
  }, [folder])

  const addFiles = (incoming: FileList | File[]) => {
    const all = Array.from(incoming)
    const mdFiles = all.filter(f => f.name.endsWith('.md'))
    const dropped = all.length - mdFiles.length
    if (dropped > 0) setSkippedCount(prev => prev + dropped)
    setQueuedFiles(prev => {
      const seen = new Set(prev.map(q => q.file.name))
      const fresh: QueuedFile[] = mdFiles
        .filter(f => !seen.has(f.name))
        .map(f => ({
          file: f,
          status: existingPages.has(f.name) ? 'conflict' : 'ready',
        }))
      return [...prev, ...fresh]
    })
  }

  const setResolution = (filename: string, resolution: ConflictResolution) => {
    setQueuedFiles(prev =>
      prev.map(q =>
        q.file.name === filename
          ? { ...q, resolution, renameValue: typeof resolution === 'object' ? (q.renameValue ?? '') : undefined }
          : q
      )
    )
  }

  const setRenameValue = (filename: string, value: string) => {
    setQueuedFiles(prev =>
      prev.map(q =>
        q.file.name === filename
          ? { ...q, renameValue: value, resolution: { rename: value } }
          : q
      )
    )
  }

  const isRenameConflict = (q: QueuedFile): boolean => {
    if (typeof q.resolution !== 'object' || !q.resolution.rename) return false
    const target = q.resolution.rename
    if (!target.endsWith('.md')) return true
    const otherNames = queuedFiles
      .filter(other => other.file.name !== q.file.name)
      .map(other =>
        typeof other.resolution === 'object' && other.resolution.rename
          ? other.resolution.rename
          : other.file.name
      )
    return existingPages.has(target) || otherNames.includes(target)
  }

  const pendingFiles = queuedFiles.filter(q => q.status !== 'imported')

  const canImport =
    pendingFiles.length > 0 &&
    !importing &&
    pendingFiles.every(q => {
      if (q.status === 'conflict' && !q.resolution) return false
      if (typeof q.resolution === 'object') {
        return !!q.resolution.rename?.endsWith('.md') && !isRenameConflict(q)
      }
      return true
    })

  const handleImport = async () => {
    setImporting(true)
    const formData = new FormData()
    formData.append('folder', folder)
    const resolutions: Record<string, ConflictResolution> = {}
    for (const q of pendingFiles) {
      formData.append('files', q.file)
      if (q.resolution) resolutions[q.file.name] = q.resolution
    }
    formData.append('conflict_resolutions', JSON.stringify(resolutions))

    try {
      const res = await fetch(`${API_BASE}/wiki/import`, { method: 'POST', body: formData })
      const data = await res.json()
      setQueuedFiles(prev =>
        prev.map(q => {
          const resolvedName = typeof q.resolution === 'object' && q.resolution.rename
            ? q.resolution.rename
            : q.file.name
          const rel = `${folder}/${resolvedName}`
          if ((data.imported as string[])?.includes(rel)) return { ...q, status: 'imported' }
          if ((data.skipped as string[])?.includes(q.file.name)) return { ...q, status: 'imported' }
          const err = (data.errors as Record<string, string>)?.[q.file.name]
          if (err) return { ...q, status: 'error', errorMessage: err }
          return q
        })
      )
      if (!data.errors || Object.keys(data.errors).length === 0) {
        onImported()
        onClose()
      }
    } catch {
      // network error — leave modal open for retry
    } finally {
      setImporting(false)
    }
  }

  const importCount = pendingFiles.filter(q => q.resolution !== 'skip').length

  return (
    <div style={{ position: 'fixed', inset: 0, backgroundColor: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 50 }}>
      <div style={{ backgroundColor: 'white', borderRadius: '0.5rem', width: '100%', maxWidth: '28rem', maxHeight: '90vh', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        <div className="flex items-center justify-between p-4 border-b border-gray-100 dark:border-gray-800 flex-shrink-0">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">Import into "{folder}"</h2>
          <button onClick={onClose} className="p-1 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 rounded">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-4 flex flex-col gap-3">
          <div
            onDragOver={e => { e.preventDefault(); setIsDragging(true) }}
            onDragLeave={() => setIsDragging(false)}
            onDrop={e => { e.preventDefault(); setIsDragging(false); addFiles(e.dataTransfer.files) }}
            onClick={() => fileInputRef.current?.click()}
            className={`border-2 border-dashed rounded-lg p-6 text-center cursor-pointer transition-colors ${isDragging ? 'border-blue-400 bg-blue-50 dark:bg-blue-900/20' : 'border-gray-300 dark:border-gray-600 hover:border-gray-400'}`}
          >
            <Upload className="w-6 h-6 text-gray-400 mx-auto mb-1" />
            <p className="text-sm text-gray-500 dark:text-gray-400">Drop .md files here or click to browse</p>
            <input ref={fileInputRef} type="file" accept=".md" multiple className="hidden" onChange={e => { if (e.target.files) addFiles(e.target.files) }} />
          </div>

          {skippedCount > 0 && (
            <p className="text-xs text-amber-600 dark:text-amber-400">
              {skippedCount} file{skippedCount > 1 ? 's' : ''} skipped — only .md files are accepted
            </p>
          )}

          {queuedFiles.length > 0 && (
            <div className="border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden divide-y divide-gray-100 dark:divide-gray-700">
              {queuedFiles.map(q => (
                <div
                  key={q.file.name}
                  className={`p-2.5 ${q.status === 'conflict' ? 'bg-yellow-50 dark:bg-yellow-900/20' : q.status === 'error' ? 'bg-red-50 dark:bg-red-900/20' : ''}`}
                >
                  <div className="flex items-center justify-between gap-2">
                    <div className="flex items-center gap-2 min-w-0">
                      <FileText className="w-3.5 h-3.5 text-gray-400 flex-shrink-0" />
                      <span className="text-sm text-gray-700 dark:text-gray-300 truncate">{q.file.name}</span>
                    </div>
                    <div className="flex-shrink-0">
                      {q.status === 'ready' && <span className="text-xs text-green-600 dark:text-green-400">Ready</span>}
                      {q.status === 'imported' && <CheckCircle className="w-4 h-4 text-green-500" />}
                      {q.status === 'error' && <span className="text-xs text-red-600 dark:text-red-400">{q.errorMessage}</span>}
                      {q.status === 'conflict' && !q.resolution && (
                        <div className="flex items-center gap-1">
                          <AlertTriangle className="w-3.5 h-3.5 text-yellow-500" />
                          <button onClick={() => setResolution(q.file.name, 'overwrite')} className="text-xs px-1.5 py-0.5 border border-gray-200 dark:border-gray-600 rounded hover:bg-gray-50 dark:hover:bg-gray-700 dark:text-gray-300">Overwrite</button>
                          <button onClick={() => setResolution(q.file.name, 'skip')} className="text-xs px-1.5 py-0.5 border border-gray-200 dark:border-gray-600 rounded hover:bg-gray-50 dark:hover:bg-gray-700 dark:text-gray-300">Skip</button>
                          <button onClick={() => setResolution(q.file.name, { rename: '' })} className="text-xs px-1.5 py-0.5 border border-gray-200 dark:border-gray-600 rounded hover:bg-gray-50 dark:hover:bg-gray-700 dark:text-gray-300">Rename…</button>
                        </div>
                      )}
                      {q.status === 'conflict' && q.resolution === 'overwrite' && <span className="text-xs text-blue-600 dark:text-blue-400">Overwrite</span>}
                      {q.status === 'conflict' && q.resolution === 'skip' && <span className="text-xs text-gray-400">Skip</span>}
                    </div>
                  </div>
                  {q.status === 'conflict' && typeof q.resolution === 'object' && (
                    <div className="mt-1.5 pl-5">
                      <input
                        type="text"
                        value={q.renameValue ?? ''}
                        onChange={e => setRenameValue(q.file.name, e.target.value)}
                        placeholder="new-filename.md"
                        className={`text-xs w-full border rounded px-2 py-1 dark:bg-gray-800 dark:text-gray-200 ${isRenameConflict(q) ? 'border-red-400' : 'border-gray-300 dark:border-gray-600'}`}
                      />
                      {isRenameConflict(q) && (
                        <p className="text-xs text-red-500 dark:text-red-400 mt-0.5">That name is already taken</p>
                      )}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        <div style={{ padding: '12px 16px', borderTop: '1px solid #f3f4f6', display: 'flex', justifyContent: 'flex-end', flexShrink: 0 }}>
          <button
            onClick={handleImport}
            disabled={!canImport}
            className="px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
          >
            {importing && <Loader2 className="w-4 h-4 animate-spin" />}
            {importCount > 0 ? `Import ${importCount} file${importCount > 1 ? 's' : ''}` : 'Import'}
          </button>
        </div>
      </div>
    </div>
  )
}
