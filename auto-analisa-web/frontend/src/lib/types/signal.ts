export type TFMap = { trend: string; pattern: string; trigger: string };
export type STFlip = { ts: string | null; side: 'BUY' | 'SELL' | null; price: number | null };
export type MiniPoint = { ts: number; close: number };
export type STBlock = { tf: string; trend: number; signal: number; line: number; up: number; dn: number; last_flip: STFlip; mini?: MiniPoint[] };
export type Scores = { trend: number; pattern: number; trigger: number };
export type IndicatorSet = { ST: number; EMA50: number; RSI: number; MACD: number };
export type Indicators = { trend: IndicatorSet; pattern: IndicatorSet; trigger: IndicatorSet };
export type Weights = { groups: Scores; indicators: { trend: Record<string, number>; pattern: Record<string, number>; trigger: Record<string, number> } };

export interface SignalRow {
  symbol: string;
  mode: 'fast'|'medium'|'swing';
  timestamp: string;
  tf_map: TFMap;
  btc_bias: { score: number; direction: 'LONG'|'SHORT'|'NEUTRAL'; threshold: number };
  st: { trend: STBlock; pattern: STBlock; trigger: STBlock };
  indicators: Indicators;
  scores: Scores;
  weights: Weights;
  total_score: number;
  signal: { side: 'LONG'|'SHORT'|'NO_TRADE'; strength: 'WEAK'|'MEDIUM'|'STRONG'|'EXTREME'|'NONE'; confidence: number };
  metadata: { strict_bias: boolean };
  error?: string;
}

