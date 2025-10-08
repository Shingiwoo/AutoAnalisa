export type FundingCtx = { rate: number; score: -1|0|1 };
export type AltBTC = { label: string; dir: 'LONG'|'SHORT'|'NEUTRAL'; boost: number; risk_mult: number };
export type BTCDCtx = { dir: 'LONG'|'SHORT'|'NEUTRAL'; boost: number };
export type PriceOI = { label: 'NAIK KUAT'|'NAIK LEMAH'|'TURUN KUAT'|'TURUN LEMAH'; boost: number };
export type ContextBlock = { funding: FundingCtx; alt_btc: AltBTC; btcd?: BTCDCtx | null; price_oi: PriceOI };

