-- Phase 4: current weather at each fire event (fire-relevant parameters).
-- Weather is time varying, so we keep the observation time and when it was fetched.

CREATE TABLE IF NOT EXISTS fire_event_weather (
  event_id       bigint PRIMARY KEY REFERENCES fire_event(id) ON DELETE CASCADE,
  temp_c         double precision,   -- 2 m air temperature, Celsius
  rh             double precision,   -- relative humidity, percent
  dew_point_c    double precision,   -- 2 m dew point, Celsius
  wind_speed_kmh double precision,   -- 10 m wind speed
  wind_dir_deg   double precision,   -- 10 m wind direction (from)
  wind_gust_kmh  double precision,   -- 10 m wind gusts
  precip_mm      double precision,   -- precipitation
  pressure_hpa   double precision,   -- surface pressure
  soil_moist_surface double precision, -- soil moisture 0-1 cm, m3/m3
  soil_moist_root    double precision, -- soil moisture 3-9 cm, m3/m3
  soil_temp_c        double precision, -- soil temperature 0 cm, Celsius
  vpd_kpa            double precision, -- vapour pressure deficit (dryness), kPa
  weather_time   timestamptz,        -- valid time reported by the provider
  fetched_at     timestamptz NOT NULL DEFAULT now()
);
