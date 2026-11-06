import { expect, test } from 'vitest'

import {
  NOT_AVAILABLE,
  count,
  dateTime,
  decimal,
  groupIndian,
  isZero,
  percentOf,
  rupees,
} from '../src/format'

test('digits are grouped the Indian way: three, then pairs', () => {
  expect(groupIndian('0')).toBe('0')
  expect(groupIndian('999')).toBe('999')
  expect(groupIndian('1000')).toBe('1,000')
  expect(groupIndian('12345')).toBe('12,345')
  expect(groupIndian('100000')).toBe('1,00,000')
  expect(groupIndian('1234567')).toBe('12,34,567')
  expect(groupIndian('10000000')).toBe('1,00,00,000')
  expect(groupIndian('123456789012345')).toBe('12,34,56,78,90,12,345')
})

test('a rupee amount keeps the backend’s digits exactly', () => {
  expect(rupees('0.00')).toBe('₹0.00')
  expect(rupees('10000.00')).toBe('₹10,000.00')
  expect(rupees('250000.00')).toBe('₹2,50,000.00')
  expect(rupees('400000.01')).toBe('₹4,00,000.01')
  expect(rupees('12345678.9')).toBe('₹1,23,45,678.90')
  expect(rupees('5')).toBe('₹5.00')
  // Larger than a floating-point number can hold exactly: every digit survives.
  expect(rupees('999999999999999.99')).toBe('₹99,99,99,99,99,99,999.99')
})

test('a negative amount carries its sign, and zero never does', () => {
  expect(rupees('-10000.00')).toBe('-₹10,000.00')
  expect(rupees('-0.01')).toBe('-₹0.01')
  expect(rupees('-0.00')).toBe('₹0.00')
  expect(decimal('-1234567.5')).toBe('-12,34,567.50')
})

test('decimals are padded and never rounded away', () => {
  expect(decimal('1234.5')).toBe('1,234.50')
  expect(decimal('1234')).toBe('1,234.00')
  expect(decimal('0.05', 2)).toBe('0.05')
  expect(decimal('0.0375', 2)).toBe('0.0375') // more digits than asked for: all are kept
  expect(decimal('007.10')).toBe('7.10')
  expect(decimal('12', 0)).toBe('12')
})

test('a missing or unreadable figure is shown as not available, never as zero', () => {
  for (const value of [null, undefined, '', 'abc', '1,000.00', '1e5', '₹5', '1.2.3']) {
    expect(rupees(value)).toBe(NOT_AVAILABLE)
    expect(decimal(value)).toBe(NOT_AVAILABLE)
  }
})

test('a percentage is exact and rounds half up', () => {
  expect(percentOf('10000.00', '250000.00')).toBe('4.0%')
  expect(percentOf('250000.00', '250000.00')).toBe('100.0%')
  // 99.9999975: below the line, so rounding stops short of 100 at any precision (S6).
  expect(percentOf('399999.99', '400000.00', 2)).toBe('99.99%')
  expect(percentOf('399999.99', '400000.00', 4)).toBe('99.9999%')
  expect(percentOf('399999.99', '400000.00', 6)).toBe('99.999998%') // ...9975: half up
  expect(percentOf('399999.99', '400000.00', 7)).toBe('99.9999975%') // exact
  expect(percentOf('1.00', '3.00', 2)).toBe('33.33%')
  expect(percentOf('2.00', '3.00', 2)).toBe('66.67%')
  expect(percentOf('1.00', '8.00', 1)).toBe('12.5%')
  expect(percentOf('1.00', '16.00', 1)).toBe('6.3%') // 6.25, half up
  expect(percentOf('0.00', '400000.00')).toBe('0.0%')
  expect(percentOf('1.00', '3.00', 0)).toBe('33%')
})

// S6: the screen may not say a line is reached when the backend says it is not.

test('a figure just below the line never reads as 100%', () => {
  // 2,49,990 against PM 2,50,000 is 99.996%, which half up would show as 100.0%.
  expect(percentOf('249990.00', '250000.00')).toBe('99.9%')
  expect(percentOf('249999.99', '250000.00')).toBe('99.9%')
  // 99.95% exactly is where half up first reaches 100.0%.
  expect(percentOf('249875.00', '250000.00')).toBe('99.9%')
  expect(percentOf('399999.99', '400000.00')).toBe('99.9%')
  expect(percentOf('12499.99', '12500.00')).toBe('99.9%')
  // The size is what is compared, so a negative effect is held back the same way.
  expect(percentOf('-249990.00', '250000.00')).toBe('99.9%')
  expect(percentOf('249990.00', '-250000.00')).toBe('99.9%')
  // At another precision it is the largest percentage below 100 at that precision.
  expect(percentOf('249999.00', '250000.00', 0)).toBe('99%')
  expect(percentOf('249999.99', '250000.00', 3)).toBe('99.999%')
})

test('a figure exactly at the line still reads as 100%', () => {
  expect(percentOf('250000.00', '250000.00')).toBe('100.0%')
  expect(percentOf('400000.00', '400000.00')).toBe('100.0%')
  expect(percentOf('12500.00', '12500.00')).toBe('100.0%')
  expect(percentOf('-250000.00', '250000.00')).toBe('100.0%')
  expect(percentOf('250000', '250000.00')).toBe('100.0%')
  expect(percentOf('250000.00', '250000.00', 0)).toBe('100%')
})

test('a figure above the line reads as 100% or more, rounded as before', () => {
  expect(percentOf('250000.01', '250000.00')).toBe('100.0%')
  expect(percentOf('250124.99', '250000.00')).toBe('100.0%') // 100.049996
  expect(percentOf('250125.00', '250000.00')).toBe('100.1%') // 100.05, half up
  expect(percentOf('400000.00', '250000.00')).toBe('160.0%')
  expect(percentOf('-400000.01', '400000.00')).toBe('100.0%')
})

test('rounding everywhere else below the line is unchanged', () => {
  expect(percentOf('249874.99', '250000.00')).toBe('99.9%') // 99.949996, ordinary rounding
  expect(percentOf('249625.00', '250000.00')).toBe('99.9%') // 99.85, half up
  expect(percentOf('249624.99', '250000.00')).toBe('99.8%') // 99.849996
  expect(percentOf('124875.00', '250000.00')).toBe('50.0%') // 49.95, half up
  expect(percentOf('203000.00', '400000.00')).toBe('50.8%') // 50.75, half up
  expect(percentOf('100.00', '400000.00')).toBe('0.0%') // 0.025: the nil end is not changed
})

test('a percentage compares sizes, so a negative effect reads against the line', () => {
  expect(percentOf('-10000.00', '250000.00')).toBe('4.0%')
  expect(percentOf('600000.00', '400000.00')).toBe('150.0%')
  expect(percentOf('1234567890.00', '1.00', 0)).toBe('1,23,45,67,89,000%')
})

test('a percentage is not offered when it cannot be computed', () => {
  expect(percentOf('1.00', '0.00')).toBeNull()
  expect(percentOf(null, '1.00')).toBeNull()
  expect(percentOf('1.00', undefined)).toBeNull()
  expect(percentOf('abc', '1.00')).toBeNull()
  expect(percentOf('1.00', 'abc')).toBeNull()
})

test('exactness holds where floating point would not', () => {
  // 0.1 + 0.2 style traps and very large amounts.
  expect(percentOf('0.07', '0.10', 1)).toBe('70.0%')
  expect(percentOf('999999999999999.99', '999999999999999.99', 3)).toBe('100.000%')
  expect(percentOf('333333333333333.33', '999999999999999.99', 6)).toBe('33.333333%')
})

test('a date and time reads the way the firm writes it', () => {
  expect(dateTime('2026-11-05T05:54:53+00:00', 'UTC')).toBe('5 Nov 2026, 05:54')
  expect(dateTime('2026-11-05T11:24:53+05:30', 'Asia/Kolkata')).toBe('5 Nov 2026, 11:24')
  expect(dateTime('2026-11-05T05:54:53+00:00', 'Asia/Kolkata')).toBe('5 Nov 2026, 11:24')
  expect(dateTime(null)).toBe(NOT_AVAILABLE)
  expect(dateTime('not a date')).toBe(NOT_AVAILABLE)
})

test('a count agrees with its noun', () => {
  expect(count(0, 'misstatement')).toBe('0 misstatements')
  expect(count(1, 'misstatement')).toBe('1 misstatement')
  expect(count(2, 'misstatement')).toBe('2 misstatements')
  expect(count(2, 'entry', 'entries')).toBe('2 entries')
})

test('nil is recognised however it is written, and nothing else is', () => {
  for (const nil of ['0', '0.00', '0.0', '-0.00', '000.000']) expect(isZero(nil)).toBe(true)
  for (const some of ['0.01', '-0.01', '60000.00', '1', 'nil', '']) expect(isZero(some)).toBe(false)
})

test('the largest amount the database can hold is formatted without losing a paisa', () => {
  // The money domain refuses 10^15 and above; a float cannot hold this many digits exactly.
  expect(rupees('999999999999999.99')).toBe('₹99,99,99,99,99,99,999.99')
  expect(rupees('-999999999999999.99')).toBe('-₹99,99,99,99,99,99,999.99')
  expect(rupees('900719925474099.31')).toBe('₹90,07,19,92,54,74,099.31')
  expect(decimal('123456789012345.67')).toBe('12,34,56,78,90,12,345.67')
  expect(Number('999999999999999.99').toFixed(2)).not.toBe('999999999999999.99')
})
