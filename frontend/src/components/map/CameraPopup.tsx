import React, { useCallback, useEffect, useState } from 'react';
import { Popup } from 'react-leaflet';
import { useFeedStore } from '../../store';

interface CameraPopupProps {
  cam: {
    id: string;
    name: string;
    lat: number;
    lng: number;
  };
  onClose: () => void;
}

export const CameraPopup: React.FC<CameraPopupProps> = ({ cam, onClose }) => {
  const city = useFeedStore((s) => s.city);
  const [file, setFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [feedError, setFeedError] = useState<string | null>(null);
  const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

  const clearAndClose = useCallback(() => {
    setResult(null);
    setFile(null);
    setFeedError(null);
    setError(null);
    onClose();
  }, [onClose]);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      setFile(e.target.files[0]);
      setError(null);
      setFeedError(null);
    }
  };

  const handleUpload = async () => {
    if (!file) return;
    setLoading(true);
    setError(null);
    setFeedError(null);
    setResult(null);

    const formData = new FormData();
    formData.append('file', file);
    formData.append('lat', cam.lat.toString());
    formData.append('lng', cam.lng.toString());
    formData.append('intersection_name', cam.name);
    formData.append('city', city);

    try {
      const response = await fetch(`${API_BASE}/api/surveillance/upload`, {
        method: 'POST',
        body: formData,
      });

      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(data?.detail || data?.message || `Upload failed (${response.status})`);
      }
      setResult(data);
    } catch (err: any) {
      setError(err.message || 'Error uploading video');
    } finally {
      setLoading(false);
    }
  };

  const handleDemo = async () => {
    setLoading(true);
    setError(null);
    setFeedError(null);
    setResult(null);

    const formData = new FormData();
    formData.append('lat', cam.lat.toString());
    formData.append('lng', cam.lng.toString());
    formData.append('intersection_name', cam.name);
    formData.append('city', city);

    try {
      const response = await fetch(`${API_BASE}/api/surveillance/inject-demo`, {
        method: 'POST',
        body: formData,
      });

      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(data?.detail || data?.message || `Demo failed (${response.status})`);
      }
      setResult(data);
    } catch (err: any) {
      setError(err.message || 'Error injecting demo feed');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!result?.feed_id) return;
    let stopped = false;
    const timer = setInterval(async () => {
      try {
        const res = await fetch(`${API_BASE}/api/surveillance/status/${result.feed_id}`);
        if (!res.ok) return;
        const data = await res.json();
        if (!stopped && data?.status === 'completed') {
          clearAndClose();
        }
      } catch {
        // Network hiccups are ignored; polling continues.
      }
    }, 1200);

    return () => {
      stopped = true;
      clearInterval(timer);
    };
  }, [API_BASE, result?.feed_id, clearAndClose]);

  return (
    <Popup
      position={[cam.lat, cam.lng]}
      eventHandlers={{ remove: onClose }}
      closeOnClick={false}
      minWidth={340}
      maxWidth={420}
    >
      <div
        className="bg-[#111111] text-gray-200 font-mono p-0 rounded-lg overflow-hidden min-w-[320px]"
        onClick={(e) => e.stopPropagation()}
        onMouseDown={(e) => e.stopPropagation()}
      >
        <div className="flex justify-between items-center bg-[#0a0a0a] px-3 py-2 border-b border-gray-800">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-red-500 animate-pulse" />
            <span className="text-xs font-bold text-gray-300">REC / CCTV-{cam.id}</span>
          </div>
          <span className="text-[10px] text-gray-500 max-w-[150px] truncate">{cam.name}</span>
        </div>

        <div className="p-3">
          {result ? (
            <div className="flex flex-col gap-2">
              <div className="relative aspect-video bg-black border border-gray-800 rounded">
                {!feedError ? (
                  <img
                    src={`${API_BASE}/api/surveillance/feed/${result.feed_id}`}
                    alt="Live Inference Feed"
                    className="w-full h-full object-contain"
                    onError={() =>
                      setFeedError('Live feed unavailable. Try another video file or re-inject.')
                    }
                  />
                ) : (
                  <div className="w-full h-full flex flex-col items-center justify-center text-center px-3 gap-2">
                    <span className="text-[10px] text-amber-300">{feedError}</span>
                    <button
                      type="button"
                      onClick={() => {
                        setResult(null);
                        setFile(null);
                        setFeedError(null);
                      }}
                      className="text-[10px] py-1 px-2 bg-gray-800 hover:bg-gray-700 rounded transition-colors"
                    >
                      Retry Upload
                    </button>
                  </div>
                )}
              </div>
              <button
                type="button"
                onClick={clearAndClose}
                className="w-full mt-2 text-xs py-1.5 bg-gray-800 hover:bg-gray-700 rounded text-center transition-colors"
              >
                Clear Feed
              </button>
            </div>
          ) : (
            <div className="flex flex-col gap-3">
              <div className="aspect-video bg-[#0a0a0a] border border-gray-800 rounded flex flex-col items-center justify-center text-center p-4">
                <span className="text-2xl mb-2 text-gray-600">📡</span>
                <span className="text-xs text-gray-500 uppercase tracking-widest font-bold">Signal Lost</span>
                <span className="text-[10px] text-gray-600 mt-1">Upload external feed</span>
              </div>

              <div className="flex flex-col gap-2">
                <input
                  type="file"
                  accept="video/mp4,video/x-m4v,video/*"
                  onChange={handleFileChange}
                  className="w-full text-[10px] text-gray-400 file:cursor-pointer file:mr-2 file:py-1 file:px-2 file:rounded file:border-0 file:text-[10px] file:font-semibold file:bg-gray-800 file:text-gray-300 hover:file:bg-gray-700"
                />
                <button
                  type="button"
                  onClick={handleUpload}
                  disabled={!file || loading}
                  className="w-full py-1.5 text-xs font-bold rounded flex justify-center items-center bg-blue-600/90 hover:bg-blue-600 text-white disabled:bg-gray-800 disabled:text-gray-600 transition-colors"
                >
                  {loading ? 'INFERENCE RUNNING...' : 'INJECT FEED'}
                </button>

                <button
                  type="button"
                  onClick={handleDemo}
                  disabled={loading}
                  className="w-full py-1.5 text-xs font-bold rounded flex justify-center items-center bg-gray-800 hover:bg-gray-700 text-gray-300 transition-colors border border-gray-700"
                >
                  {loading ? 'PREPARING...' : 'PLAY DEMO'}
                </button>
              </div>

              {error && <div className="text-[10px] text-red-400 bg-red-900/20 p-2 rounded">ERROR: {error}</div>}
            </div>
          )}
        </div>
      </div>
    </Popup>
  );
};
