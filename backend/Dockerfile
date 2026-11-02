# Build context is the repo root so shared/ is available. See docker-compose.yml.
FROM node:20-alpine
WORKDIR /app
COPY backend/package.json ./
RUN npm install --omit=dev
COPY shared/js ./shared/js
COPY backend/ ./
EXPOSE 3040
CMD ["npm", "start"]
