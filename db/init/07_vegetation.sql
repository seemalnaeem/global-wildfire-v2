-- Phase 4: vegetation indices per fire event, from Sentinel-2 (Copernicus).
-- Values are the most recent cloud-free observation near the event.

CREATE TABLE IF NOT EXISTS fire_event_vegetation (
  event_id   bigint PRIMARY KEY REFERENCES fire_event(id) ON DELETE CASCADE,
  ndvi       double precision,   -- greenness, -1..1
  ndmi       double precision,   -- moisture, -1..1
  nbr        double precision,   -- burn ratio, -1..1
  obs_date   timestamptz,        -- date of the Sentinel-2 observation used
  fetched_at timestamptz NOT NULL DEFAULT now()
);
