import { Router } from 'express';
import { getStatus } from '../controllers/status.js';

export const status = Router();

status.get('/', getStatus);
