# Build context is the repo root so shared/ is available. See docker-compose.yml.
FROM node:20-alpine
WORKDIR /app
COPY frontend/package.json ./
RUN npm install
COPY shared/js ./shared/js
COPY frontend/ ./
EXPOSE 5180
CMD ["npm", "run", "dev"]
