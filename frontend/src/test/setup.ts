import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach } from 'vitest'

// testing-library's automatic cleanup only registers when vitest globals
// are enabled; with explicit imports we register it ourselves.
afterEach(() => {
  cleanup()
})