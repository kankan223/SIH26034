import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach } from 'vitest'
import { QueryClient } from '@tanstack/react-query'

let queryClient: QueryClient | undefined

afterEach(() => {
  cleanup()
  queryClient?.clear()
})

// TestWrapper is defined inline in each test file.
// This file only provides cleanup and the jest-dom matchers.
