import cors from 'cors';

// Allow the frontend origin. Extend for deployed hosts via env.
const origins = [process.env.FRONTEND_ORIGIN || 'http://172.18.1.60:5180'];

export const corsAllow = cors({ origin: origins });
