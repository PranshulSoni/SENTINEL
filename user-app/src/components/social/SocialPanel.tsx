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
    <div
      className="h-full overflow-y-auto px-4 py-4 pb-24 space-y-4"
      style={{ background: 'var(--color-bg)' }}
    >
      {/* ── Identity Panel ── */}
      <div
        className="p-4"
        style={{
          background: 'var(--color-surface)',
          border: '1px solid var(--color-border)',
        }}
      >
        <div className="flex items-center gap-2 mb-3">
          <Users className="w-3.5 h-3.5" style={{ color: 'var(--color-accent)' }} />
          <span
            className="text-[10px] font-bold uppercase tracking-[0.14em]"
            style={{ color: 'var(--color-text-secondary)' }}
          >
            Social Access · {cityLabel}
          </span>
        </div>

        {isLoggedIn ? (
          <div
            className="flex items-center justify-between gap-3 p-3"
            style={{
              background: 'var(--color-accent-dim)',
              border: '1px solid var(--color-accent)',
            }}
          >
            <div className="min-w-0">
              <div
                className="text-[9px] font-mono uppercase tracking-wider mb-0.5"
                style={{ color: 'var(--color-text-secondary)' }}
              >
                LOGGED IN AS
              </div>
              <div className="flex items-center gap-2">
                <UserCheck className="w-3.5 h-3.5 shrink-0" style={{ color: 'var(--color-accent)' }} />
                <span className="text-sm font-bold truncate" style={{ color: 'var(--color-text)' }}>
                  {selectedUser}
                </span>
              </div>
            </div>
            <button
              onClick={() => setSelectedUser('')}
              className="shrink-0 flex items-center gap-1.5 px-3 py-1.5 text-[10px] font-bold uppercase tracking-wider font-mono transition-colors"
              style={{
                border: '1px solid var(--color-border)',
                color: 'var(--color-text-secondary)',
                background: 'var(--color-surface)',
              }}
            >
              <LogOut className="w-3 h-3" />
              Log out
            </button>
          </div>
        ) : (
          <p
            className="text-xs font-mono"
            style={{ color: 'var(--color-text-secondary)' }}
          >
            No social user logged in.
          </p>
        )}

        <div className="mt-3 space-y-1.5">
          <div
            className="text-[9px] font-mono uppercase tracking-wider mb-2"
            style={{ color: 'var(--color-text-secondary)' }}
          >
            LOG IN AS
          </div>
          {cityUsers.map((u) => {
            const isActive = selectedUser === u.name;
            return (
              <button
                key={`${u.city}-${u.name}`}
                onClick={() => setSelectedUser(u.name)}
                className="w-full text-left px-3 py-2.5 text-sm font-medium transition-all"
                style={{
                  background: isActive ? 'var(--color-accent)' : 'var(--color-bg)',
                  border: `1px solid ${isActive ? 'var(--color-accent)' : 'var(--color-border)'}`,
                  color: isActive ? '#fff' : 'var(--color-text)',
                }}
              >
                {u.name}
              </button>
            );
          })}
        </div>
      </div>

      {/* ── Alerts ── */}
      <div className="flex items-center gap-2">
        <Megaphone className="w-3.5 h-3.5" style={{ color: 'var(--color-accent)' }} />
        <span
          className="text-[10px] font-bold uppercase tracking-[0.14em]"
          style={{ color: 'var(--color-text-secondary)' }}
        >
          City Social Alerts
        </span>
      </div>

      {loading ? (
        <p
          className="text-[11px] font-mono"
          style={{ color: 'var(--color-text-secondary)' }}
        >
          Loading alerts...
        </p>
      ) : alerts.length === 0 ? (
        <div
          className="p-4 text-sm"
          style={{
            border: '1px solid var(--color-border)',
            color: 'var(--color-text-secondary)',
          }}
        >
          No social alerts for {cityLabel} right now.
        </div>
      ) : (
        <div className="space-y-2">
          {alerts.map((a) => (
            <div
              key={a._id || `${a.published_at}-${a.message.slice(0, 12)}`}
              className="p-3"
              style={{
                background: 'var(--color-surface)',
                border: '1px solid var(--color-border)',
                borderLeft: '2px solid var(--color-accent)',
              }}
            >
              <div className="flex items-center justify-between mb-2">
                <span
                  className="text-[9px] font-bold uppercase tracking-wider font-mono"
                  style={{ color: 'var(--color-accent)' }}
                >
                  PUBLIC ALERT
                </span>
                <span
                  className="text-[9px] font-mono"
                  style={{ color: 'var(--color-text-secondary)' }}
                >
                  {formatTime(a.published_at)}
                </span>
              </div>
              <p className="text-sm font-medium leading-relaxed" style={{ color: 'var(--color-text)' }}>
                {a.message}
              </p>
              <div
                className="mt-2 flex items-center gap-2 text-[10px] font-mono"
                style={{ color: 'var(--color-text-secondary)' }}
              >
                <BellRing className="w-3 h-3" />
                <span>
                  {a.recipient_count ?? a.recipients?.length ?? 0} users · {cityLabel}
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
