// What the items that are clearly trivial one by one come to together (backend D56, D57).
// The totals, the comparison with the clearly-trivial threshold and whether the items were
// accumulated are all the backend's; nothing is added up or decided here.
import type { NotAccumulatedTotal } from '../api'
import { rupees } from '../format'

export function NotAccumulated({ total }: { total: NotAccumulatedTotal }) {
  const together = (
    <>
      {rupees(total.profit_before_tax_gross)} gross on profit before tax and{' '}
      {rupees(total.net_assets_gross)} gross on net assets
    </>
  )
  if (total.accumulated_together.length > 0) {
    return (
      <p
        role="note"
        className="rounded border border-amber-200 bg-amber-50 px-2 py-1.5 text-amber-900"
      >
        Clearly trivial one by one, accumulated together: {total.accumulated_together.join(', ')}.
        Together they come to {together}, which reaches the clearly-trivial threshold (
        {rupees(total.ctt)}). SA 450 paragraph A2 treats items as clearly trivial only where they
        are clearly inconsequential individually and in aggregate, so all of them are in the totals
        and the gates.
      </p>
    )
  }
  return (
    <p>
      Together they come to {together}. They stay out while that is below the clearly-trivial
      threshold on both; once it reaches the threshold on either, all of them are accumulated.
    </p>
  )
}
