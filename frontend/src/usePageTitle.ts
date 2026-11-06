// The browser's title for the screen in view, so a tab, a history entry and a screen reader
// each say where a person is. The application's name always follows the screen's.
import { useEffect } from 'react'

export const APP_NAME = 'Misstatements Rollup'

export function usePageTitle(screen: string | null): void {
  useEffect(() => {
    document.title = screen === null || screen === '' ? APP_NAME : `${screen} · ${APP_NAME}`
  }, [screen])
}
