import React, { useEffect, useMemo, useState } from 'react';
import { Megaphone, Users, BellRing, LogOut, UserCheck } from 'lucide-react';
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

const CITY_OPTION_LIMIT: Record<CityCode, number> = {
  nyc: 2,
  chandigarh: 3,
};

const FALLBACK_USERS: Record<CityCode, SocialUser[]> = {
  chandigarh: [
    { name: 'Arjun Mehta', city: 'chandigarh' },
    { name: 'Priya Sharma', city: 'chandigarh' },
    { name: 'Rohit Bhatia', city: 'chandigarh' },
  ],
  nyc: [
    { name: 'Maya Thompson', city: 'nyc' },
    { name: 'Daniel Rivera', city: 'nyc' },
  ],
};

const getSessionKey = (city: CityCode): string => `sentinel.social.session.${city}`;

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
  const cityCode = city as CityCode;

  const cityLabel = useMemo(
    () => (city === 'nyc' ? 'New York' : 'Chandigarh'),
    [city]
  );

  const cityUsers = useMemo(() => {
    const limited = users
      .filter((u) => u.city === cityCode)
      .slice(0, CITY_OPTION_LIMIT[cityCode]);
    if (limited.length > 0) return limited;
    return FALLBACK_USERS[cityCode];
  }, [cityCode, users]);

  const isLoggedIn = Boolean(selectedUser);

  useEffect(() => {
    let cancelled = false;
    api.getSocialUsers(cityCode)
      .then((data) => {
        if (cancelled) return;
        const list = Array.isArray(data) ? data : [];
        const scoped = list
          .filter((u: SocialUser) => u.city === cityCode)
          .slice(0, CITY_OPTION_LIMIT[cityCode]);
        const finalUsers = scoped.length > 0 ? scoped : FALLBACK_USERS[cityCode];
        const storedUser = window.localStorage.getItem(getSessionKey(cityCode)) || '';

        setUsers(finalUsers);
        setSelectedUser((current) => {
          const active = current || storedUser;
          if (active && finalUsers.some((u: SocialUser) => u.name === active)) {
            return active;
          }
          return '';
        });
      })
      .catch(() => {
        if (!cancelled) {
          const fallback = FALLBACK_USERS[cityCode];
          const storedUser = window.localStorage.getItem(getSessionKey(cityCode)) || '';
          setUsers(fallback);
          setSelectedUser(
            storedUser && fallback.some((u: SocialUser) => u.name === storedUser)
              ? storedUser
              : '',
          );
        }
      });
    return () => {
      cancelled = true;
    };
  }, [cityCode]);

  useEffect(() => {
    const key = getSessionKey(cityCode);
    if (selectedUser) {
      window.localStorage.setItem(key, selectedUser);
      return;
    }
    window.localStorage.removeItem(key);
  }, [cityCode, selectedUser]);

  useEffect(() => {
    let cancelled = false;
    const fetchAlerts = async () => {
      setLoading(true);
      try {
        const data = await api.getSocialAlerts(cityCode, selectedUser || undefined);
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
  }, [cityCode, selectedUser]);

  return (
    <div className="h-full overflow-y-auto px-6 py-6 pb-24">
      <div className="bg-white rounded-2xl border border-gray-100 p-4 shadow-sm mb-4">
        <div className="flex items-center gap-2 mb-3">
          <Users className="w-4 h-4 text-[#FF5A5F]" />
          <span className="text-xs font-bold uppercase tracking-wider text-gray-500">
            Social Access ({cityLabel})
          </span>
        </div>

        <div className="rounded-xl border border-gray-200 bg-gray-50 p-3">
          {isLoggedIn ? (
            <div className="flex items-center justify-between gap-3">
              <div className="min-w-0">
                <div className="text-[10px] font-bold uppercase tracking-wider text-gray-400 mb-1">
                  Logged in as
                </div>
                <div className="flex items-center gap-2 text-sm font-bold text-[#1A1A1A] truncate">
                  <UserCheck className="w-4 h-4 text-[#A3B18A] shrink-0" />
                  <span className="truncate">{selectedUser}</span>
                </div>
              </div>
              <button
                onClick={() => setSelectedUser('')}
                className="shrink-0 inline-flex items-center gap-1.5 rounded-lg bg-white border border-gray-200 px-3 py-2 text-xs font-bold text-gray-600 hover:text-[#FF5A5F] hover:border-[#FF5A5F]/30 transition-colors"
              >
                <LogOut className="w-3.5 h-3.5" />
                Log out
              </button>
            </div>
          ) : (
            <div className="text-sm font-semibold text-gray-500">No social user logged in.</div>
          )}
        </div>

        <div className="mt-3">
          <div className="text-[10px] font-bold uppercase tracking-wider text-gray-400 mb-2">
            Log in as
          </div>
          <div className="space-y-2">
            {cityUsers.map((u) => {
              const isActive = selectedUser === u.name;
              return (
                <button
                  key={`${u.city}-${u.name}`}
                  onClick={() => setSelectedUser(u.name)}
                  className={`w-full text-left rounded-xl px-3 py-2.5 border text-sm font-semibold transition-all ${
                    isActive
                      ? 'border-[#FF5A5F] bg-[#FF5A5F]/10 text-[#FF5A5F]'
                      : 'border-gray-200 bg-white text-[#1A1A1A] hover:border-[#FF5A5F]/30 hover:bg-[#FF5A5F]/5'
                  }`}
                >
                  {u.name}
                </button>
              );
            })}
          </div>
        </div>
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
