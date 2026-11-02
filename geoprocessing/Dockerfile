# GDAL base gives us gdal_translate, gdalwarp, ogr2ogr, and osgeo bindings.
# Build context is the repo root so shared/ is available. See docker-compose.yml.
FROM ghcr.io/osgeo/gdal:ubuntu-small-3.9.2

WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends python3-pip \
    && rm -rf /var/lib/apt/lists/*

COPY geoprocessing/requirements.txt ./
RUN pip3 install --no-cache-dir --break-system-packages -r requirements.txt

COPY shared ./shared
COPY geoprocessing/ ./

ENV PYTHONPATH=/app
EXPOSE 3041
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "3041"]
