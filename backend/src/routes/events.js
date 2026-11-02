import { Router } from 'express';
import { listEvents, getEvent } from '../controllers/events.js';

export const events = Router();

events.get('/', listEvents);
events.get('/:id', getEvent);
