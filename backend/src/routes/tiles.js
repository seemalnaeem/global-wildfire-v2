import { Router } from 'express';
import { getMvt } from '../tiles/mvt.js';

export const tiles = Router();

// GET /tiles/:layer/:z/:x/:y.mvt
tiles.get('/:layer/:z/:x/:y.mvt', getMvt);
