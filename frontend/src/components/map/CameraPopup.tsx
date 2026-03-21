import React, { useState } from 'react';
import { Popup } from 'react-leaflet';

export const CameraPopup = ({ cam }: { cam: any }) => {
  const [file, setFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      setFile(e.target.files[0]);
    }
  };

  const handleUpload = async () => {
    if (!file) return;
    setLoading(true);
    setError(null);
    setResult(null);

    const formData = new FormData();
    formData.append('file', file);
    formData.append('lat', cam.lat.toString());
    formData.append('lng', cam.lng.toString());
    formData.append('intersection_name', cam.name);
    formData.append('city', 'nyc'); 

    try {
      const response = await fetch('http://localhost:8000/api/surveillance/upload', {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) throw new Error('Upload failed');
      const data = await response.json();
      setResult(data);
    } catch (err: any) {
      setError(err.message || 'Error uploading video');
    } finally {
      setLoading(false);
    }
  };

  // We use -m-4 to offset the default Leaflet popup padding
  return (
    <Popup minWidth={350} maxWidth={400}>
      <div className="bg-[#111111] text-gray-200 font-mono -m-[14px] p-0 rounded-lg overflow-hidden border border-gray-700 shadow-2xl">
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
                <img 
                  src={`http://localhost:8000/api/surveillance/feed/${result.feed_id}`} 
                  alt="Live Inference Feed"
                  className="w-full h-full object-contain"
                />
              </div>
              <button
                onClick={() => { setResult(null); setFile(null); }}
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
                  onClick={handleUpload}
                  disabled={!file || loading}
                  className="w-full py-1.5 text-xs font-bold rounded flex justify-center items-center bg-blue-600/90 hover:bg-blue-600 text-white disabled:bg-gray-800 disabled:text-gray-600 transition-colors"
                >
                  {loading ? 'RUNNING YOLO V8...' : 'INJECT FEED'}
                </button>
              </div>
              
              {error && (
                <div className="text-[10px] text-red-400 bg-red-900/20 p-2 rounded">
                  ERROR: {error}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </Popup>
  );
};
