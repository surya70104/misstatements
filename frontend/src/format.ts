// Presentation of the backend's figures. The API sends every amount as an exact decimal
// string; nothing here goes through floating point, so a figure on the screen is the figure
// the backend sent. Percentages are computed at presentation and never stored (backend D16).

const DECIMAL = /^(-?)(\d+)(?:\.(\d+))?$/

/** What a figure the backend could not give is shown as. */
export const NOT_AVAILABLE = '—'

type Parts = { negative: boolean; whole: string; fraction: string }

function parse(value: string): Parts | null {
  const match = DECIMAL.exec(value.trim())
  if (!match) return null
  const whole = (match[2] ?? '0').replace(/^0+(?=\d)/, '')
  const fraction = match[3] ?? ''
  const zero = /^0*$/.test(whole) && /^0*$/.test(fraction)
  return { negative: match[1] === '-' && !zero, whole, fraction }
}

/** Whether a decimal string is nil, however it is written: "0", "0.00", "-0.0". */
export function isZero(value: string): boolean {
  const parts = parse(value)
  return parts !== null && /^0*$/.test(parts.whole) && /^0*$/.test(parts.fraction)
}

/** Indian digit grouping: the last three digits, then pairs. 1234567 becomes 12,34,567. */
export function groupIndian(digits: string): string {
  if (digits.length <= 3) return digits
  const head = digits.slice(0, -3)
  const tail = digits.slice(-3)
  return `${head.replace(/\B(?=(\d{2})+(?!\d))/g, ',')},${tail}`
}

/**
 * A decimal string with Indian grouping and exactly `places` decimals. The digits are the
 * backend's: the value is padded with zeros, never rounded. A value with more decimals than
 * `places` is shown in full, since dropping digits would change it.
 */
export function decimal(value: string | null | undefined, places = 2): string {
  if (value === null || value === undefined) return NOT_AVAILABLE
  const parts = parse(value)
  if (!parts) return NOT_AVAILABLE
  const fraction = parts.fraction.padEnd(places, '0')
  const body =
    fraction === '' ? groupIndian(parts.whole) : `${groupIndian(parts.whole)}.${fraction}`
  return parts.negative ? `-${body}` : body
}

/** A rupee amount: ₹12,34,567.89, and -₹500.00 for a negative one. */
export function rupees(value: string | null | undefined): string {
  if (value === null || value === undefined) return NOT_AVAILABLE
  const parts = parse(value)
  if (!parts) return NOT_AVAILABLE
  const body = decimal(value, 2).replace(/^-/, '')
  return parts.negative ? `-₹${body}` : `₹${body}`
}

/** The value in hundredths of a paisa-free unit: an exact integer of `scale` decimals. */
function scaled(value: string, scale: number): bigint | null {
  const parts = parse(value)
  if (!parts || parts.fraction.length > scale) return null
  const digits = `${parts.whole}${parts.fraction.padEnd(scale, '0')}`
  const magnitude = BigInt(digits)
  return parts.negative ? -magnitude : magnitude
}

/**
 * `part` as a percentage of `whole`, computed exactly and rounded half up to `places`
 * decimals. The size of `part` is what is compared, so a negative effect reads as a
 * positive percentage of the line. Null when either figure is missing or `whole` is zero.
 *
 * A figure strictly below the line never reads as 100%: where rounding would carry it
 * there, the largest percentage below 100 at this precision is shown instead (99.9% at one
 * decimal). The line is reached only when the figure is at or above it (S6).
 */
export function percentOf(
  part: string | null | undefined,
  whole: string | null | undefined,
  places = 1,
): string | null {
  if (part === null || part === undefined || whole === null || whole === undefined) return null
  const scale = 6
  const numerator = scaled(part, scale)
  const denominator = scaled(whole, scale)
  if (numerator === null || denominator === null || denominator === 0n) return null
  const size = numerator < 0n ? -numerator : numerator
  const base = denominator < 0n ? -denominator : denominator
  const factor = 10n ** BigInt(places)
  // size / base * 100, held as an integer of `places` decimals, rounded half up.
  const halfUp = (size * 100n * factor * 2n + base) / (base * 2n)
  // 100%, as an integer of `places` decimals. Below the line, rounding may not reach it.
  const hundred = 100n * factor
  const rounded = size < base && halfUp >= hundred ? hundred - 1n : halfUp
  const text = rounded.toString().padStart(places + 1, '0')
  const whole_ = groupIndian(text.slice(0, text.length - places))
  return places === 0 ? `${whole_}%` : `${whole_}.${text.slice(-places)}%`
}

/** A date and time as the firm reads it: 5 Nov 2026, 11:24. Local time unless told otherwise. */
export function dateTime(value: string | null | undefined, timeZone?: string): string {
  if (value === null || value === undefined) return NOT_AVAILABLE
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return NOT_AVAILABLE
  return new Intl.DateTimeFormat('en-GB', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
    timeZone,
  }).format(parsed)
}

/** A count with its noun: "1 misstatement", "3 misstatements". */
export function count(value: number, singular: string, plural = `${singular}s`): string {
  return `${String(value)} ${value === 1 ? singular : plural}`
}
