import React, { useEffect, useMemo, useState } from 'react';
import { Megaphone, Users, BellRing } from 'lucide-react';
import { api } from '../../services/api';
import { useFeedStore } from '../../store';

type CityCode = 'nyc' | 'chandigarh';

interface SocialUser {
  name: string;
  city: CityCode;
}

interface SocialAlert {
  _id?: string;
  city: CityCode;
  message: string;
  incident_id?: string | null;
  operator?: string;
  published_at: string;
  recipients?: string[];
  recipient_count?: number;
}

const formatTime = (iso: string): string => {
  try {
    return new Date(iso).toLocaleString('en-US', {
      hour12: false,
      hour: '2-digit',
      minute: '2-digit',
      day: '2-digit',
      month: 'short',
    });
  } catch {
    return iso;
  }
};

const SocialPanel: React.FC = () => {
  const city = useFeedStore((s) => s.city);
  const [users, setUsers] = useState<SocialUser[]>([]);
  const [selectedUser, setSelectedUser] = useState<string>('');
  const [alerts, setAlerts] = useState<SocialAlert[]>([]);
  const [loading, setLoading] = useState(false);

  const cityLabel = useMemo(
    () => (city === 'nyc' ? 'New York' : 'Chandigarh'),
    [city]
  );

  useEffect(() => {
    let cancelled = false;
    api.getSocialUsers(city as CityCode)
      .then((data) => {
        if (cancelled) return;
        const list = Array.isArray(data) ? data : [];
        setUsers(list);
        setSelectedUser((prev) => {
          if (prev && list.some((u: SocialUser) => u.name === prev)) return prev;
          return list[0]?.name || '';
        });
      })
      .catch(() => {
        if (!cancelled) setUsers([]);
      });
    return () => {
      cancelled = true;
    };
  }, [city]);

  useEffect(() => {
    let cancelled = false;
    const fetchAlerts = async () => {
      setLoading(true);
      try {
        const data = await api.getSocialAlerts(city as CityCode, selectedUser || undefined);
        if (!cancelled) {
          setAlerts(Array.isArray(data) ? data : []);
        }
      } catch {
        if (!cancelled) setAlerts([]);
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    fetchAlerts();
    const timer = setInterval(fetchAlerts, 5000);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [city, selectedUser]);

  return (
    <div className="h-full overflow-y-auto px-6 py-6 pb-24">
      <div className="bg-white rounded-2xl border border-gray-100 p-4 shadow-sm mb-4">
        <div className="flex items-center gap-2 mb-3">
          <Users className="w-4 h-4 text-[#FF5A5F]" />
          <span className="text-xs font-bold uppercase tracking-wider text-gray-500">
            Social Profile ({cityLabel})
          </span>
        </div>
        <select
          value={selectedUser}
          onChange={(e) => setSelectedUser(e.target.value)}
          className="w-full bg-gray-50 border border-gray-200 rounded-xl px-3 py-2.5 text-sm font-semibold text-[#1A1A1A]"
        >
          {users.map((u) => (
            <option key={`${u.city}-${u.name}`} value={u.name}>
              {u.name}
            </option>
          ))}
        </select>
      </div>

      <div className="flex items-center gap-2 mb-3">
        <Megaphone className="w-4 h-4 text-[#FF5A5F]" />
        <span className="text-xs font-bold uppercase tracking-wider text-gray-500">
          City Social Alerts
        </span>
      </div>

      {loading ? (
        <div className="text-xs text-gray-400 font-semibold">Loading alerts...</div>
      ) : alerts.length === 0 ? (
        <div className="bg-white rounded-2xl border border-gray-100 p-4 text-sm text-gray-500 font-semibold">
          No social alerts for {cityLabel} right now.
        </div>
      ) : (
        <div className="space-y-3">
          {alerts.map((a) => (
            <div key={a._id || `${a.published_at}-${a.message.slice(0, 12)}`} className="bg-white rounded-2xl border border-gray-100 p-4 shadow-sm">
              <div className="flex items-center justify-between mb-2">
                <span className="text-[10px] font-bold uppercase tracking-wider text-[#FF5A5F]">Public Alert</span>
                <span className="text-[10px] font-semibold text-gray-400">{formatTime(a.published_at)}</span>
              </div>
              <p className="text-sm font-semibold text-[#1A1A1A] leading-relaxed">{a.message}</p>
              <div className="mt-3 flex items-center gap-2 text-[11px] font-semibold text-gray-500">
                <BellRing className="w-3.5 h-3.5 text-gray-400" />
                <span>
                  Sent to {a.recipient_count ?? a.recipients?.length ?? 0} users in {cityLabel}
                </span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default SocialPanel;

