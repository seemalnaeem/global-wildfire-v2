import { Router } from 'express';
import { listAlerts } from '../controllers/alerts.js';

export const alerts = Router();

alerts.get('/', listAlerts);
