// AutoAnalisa minimal types for FE (Next.js + Tailwind)

export type TFKey = '1D' | '4H' | '1H' | '15m' | '5m';
export type Bias = 'bull' | 'bear' | 'neutral';

export interface BB {
  period: number; mult: number;
  upper: number; middle: number; lower: number;
}
export interface MACD { dif: number; dea: number; hist: number; }
export interface StochRSI { k: number; d: number; }

export interface TFIndicators {
  last: number; open: number; high: number; low: number;
  close_time: string; // ISO8601
  ema?: Record<string, number>;
  bb?: BB;
  rsi?: { '6'?: number; '14'?: number; '25'?: number };
  stochrsi?: StochRSI;
  macd?: MACD;
  atr14?: number;
  vol_last?: number; vol_ma5?: number; vol_ma10?: number;
  // optional recent series (for client-side patterns if needed)
  rsi6_last5?: number[];
  close_last5?: number[];
  ema50_last5?: number[];
}

export interface ConfluenceItem {
  tf: TFKey;
  price: number;
  tags: string[];           // ['EMA20-1H','BB-mid-15m','round-number','FVG-edge',...]
  confidence?: number;      // 0..100
  distance?: number;        // |price-level|/price
  tol?: number;             // dynamic tolerance used
}

export interface LevelsContainer {
  [tf: string]: {
    support?: number[];
    resistance?: number[];
  };
  confluence?: ConfluenceItem[];
  // Optional: expose raw FVG list if needed in future
  // fvg?: { tf: TFKey; dir: 'bull' | 'bear'; top: number; bottom: number }[];
}

export interface Derivatives {
  funding_rate?: number;
  next_funding_ts?: string;
  oi?: number;
  long_short_ratio?: number;
  mark_price?: number;
  index_price?: number;
  basis_bp?: number;
}

export interface Orderbook {
  best_bid: number;
  best_ask: number;
  spread: number;
  ob_imbalance_5?: number;
}

export interface Account {
  balance_usdt: number;
  fee_maker?: number;
  fee_taker?: number;
  risk_per_trade?: number;
  leverage?: number;
  margin_mode?: 'cross' | 'isolated';
}

export interface PayloadV1 {
  symbol: string;
  exchange: string;
  market: 'spot' | 'futures';
  contract?: 'perp' | 'delivery';
  timezone?: string;              // 'Asia/Jakarta'
  account?: Account;
  open_position?: {
    side: 'long' | 'short';
    entry_price: number; qty: number;
    sl?: number; tp?: number;
    unrealized_pnl?: number;
  } | null;
  tf: Partial<Record<TFKey, TFIndicators>>;
  structure?: Record<string, any>;
  levels?: LevelsContainer;
  derivatives?: Derivatives;       // futures only
  orderbook?: Orderbook;
  // Macro & news
  session_bias?: Bias;
  btc_bias?: Bias;
  dxy_bias?: Bias;
  orderflow?: Record<string, any> | null;
  news?: Array<{ title: string; start_ts?: string; impact?: string; relevance?: string }>;
}

export interface SignalV1 {
  symbol: string;
  market: 'spot' | 'futures';
  side: 'long' | 'short';
  setup: string;
  score: number;                   // 0..100
  entry_zone: [number, number];
  invalid_level: number;
  sl: number;
  tp: string[];                    // ['+1.5%','+2.5%','+4.0%']
  tp_price: number[];              // absolute prices
  risk_per_trade?: number;
  position_sizing?: { method: string };
  notes?: string[];
  timeframe_confirmations?: { confirm_tf?: TFKey; support_tf?: TFKey };
  // UI helpers (optional)
  session_bias?: Bias;
  btc_bias?: Bias;
  confluence_bonus?: number;
}

