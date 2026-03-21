import { useEffect } from 'react';
import { useFeedStore, useIncidentStore } from '../store';
import { TrafficSegment, Incident, LLMOutput } from '../types';

export const useWebSocket = () => {
  const { city, setSegments } = useFeedStore();
  const { setIncident, setLLMOutput } = useIncidentStore();

  useEffect(() => {
    let tick = 0;
    const interval = setInterval(() => {
      tick++;
      
      // 1. Generate Mock Segments
      const segments: TrafficSegment[] = [
        {
          link_id: "1001",
          link_name: city === 'nyc' ? "Broadway & W 34th St" : "Sector 17 Chowk",
          speed: Math.max(0, 30 - tick * 2), // Mock speed drop
          status: 'OK',
          lat: city === 'nyc' ? 40.7128 : 30.7333,
          lng: city === 'nyc' ? -74.0060 : 76.7794,
        },
        {
          link_id: "1002",
          link_name: city === 'nyc' ? "7th Ave & W 34th St" : "Tribune Chowk",
          speed: 25,
          status: 'OK',
          lat: city === 'nyc' ? 40.7138 : 30.7343,
          lng: city === 'nyc' ? -74.0070 : 76.7804,
        }
      ];

      setSegments(segments);

      // 2. Mock Incident Detection (When Broadway speed drops below 10)
      if (segments[0].speed < 10 && tick > 5) {
        const incident: Incident = {
          id: "INC-999",
          city,
          status: 'active',
          severity: 'critical',
          location: { lat: segments[0].lat, lng: segments[0].lng },
          on_street: segments[0].link_name,
          cross_street: "7th Ave",
          affected_segment_ids: ["1001"],
          detected_at: new Date().toISOString(),
        };
        setIncident(incident);

        // 3. Mock LLM Intelligence Response
        const intelligence: LLMOutput = {
          signal_retiming: {
            intersections: [
              {
                name: segments[0].link_name,
                current_ns_green: 45,
                recommended_ns_green: 90,
                current_ew_green: 30,
                recommended_ew_green: 20,
                reasoning: "Heavy congestion on primary arterial due to blocked segment."
              }
            ]
          },
          diversions: {
            routes: [
              {
                priority: 1,
                name: "Diversion A",
                path: ["10th Ave", "W 42nd St", "9th Ave"],
                estimated_absorption_pct: 60,
                activate_condition: "immediate"
              }
            ]
          },
          alerts: {
            vms: "ACCIDENT AT " + segments[0].link_name.toUpperCase() + "\nEXPECT DELAYS\nUSE ALTERNATE",
            radio: "A multi-vehicle accident has been reported at " + segments[0].link_name + ". Use 10th Ave as an alternate.",
            social_media: "Traffic Alert: Incident at " + segments[0].link_name + ". #NYCTraffic #Manhattan"
          },
          narrative_update: "Incident confirmed at " + segments[0].link_name + ". LLM co-pilot has generated re-timing and diversion strategies."
        };
        setLLMOutput(intelligence);
      }
    }, 5000);

    return () => clearInterval(interval);
  }, [city, setSegments, setIncident, setLLMOutput]);
};
