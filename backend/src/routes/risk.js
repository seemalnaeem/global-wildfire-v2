import { Router } from 'express';
import { getRiskMeta } from '../controllers/risk.js';

export const risk = Router();

risk.get('/meta', getRiskMeta);
