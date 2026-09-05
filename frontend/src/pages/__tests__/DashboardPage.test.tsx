import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { DashboardPage } from '../DashboardPage'

vi.mock('../../hooks/useInspection', () => ({
  useDashboardKpis: () => ({
    data: {
      total_inspections: 142,
      compliant_count: 90,
      non_compliant_count: 37,
      flagged_for_review_count: 15,
      pending_review_count: 19,
      active_violations_count: 37,
      compliance_rate_percent: 70.9,
      total_products_categorized: 120,
      top_category: 'Food & Beverage > Packaged Food',
    },
    isLoading: false,
    isError: false,
  }),
  useDashboardTrends: () => ({
    data: { trends: [{ compliance_rate_percent: 71 }], total_months: 3 },
    isLoading: false,
    isError: false,
  }),
  useDashboardCategories: () => ({
    data: {
      categories: [
        { category: 'Food & Beverage > Packaged Food', violation_count: 22, compliance_rate_percent: 64.0 },
        { category: 'Personal Care > Toiletries', violation_count: 15, compliance_rate_percent: 78.0 },
      ],
      total_violations: 37,
    },
    isLoading: false,
    isError: false,
  }),
  useInspections: () => ({
    data: {
      items: [
        { id: 'INS-1', status: 'COMPLIANT', product_name: 'Britannia Good Day 200g' },
        { id: 'INS-2', status: 'NEEDS_HUMAN_REVIEW', product_name: 'Amul Butter 500g' },
        { id: 'INS-3', status: 'NON_COMPLIANT', product_name: 'Patanjali Atta 5kg' },
      ],
    },
    isLoading: false,
    isError: false,
  }),
}))

describe('DashboardPage (design.md §8.2)', () => {
  it('renders the four KPI figure blocks', () => {
    render(<DashboardPage />)
    expect(screen.getByText('142')).toBeInTheDocument()
    expect(screen.getByText('70.9%')).toBeInTheDocument()
    expect(screen.getByText('37')).toBeInTheDocument()
    expect(screen.getByText('19')).toBeInTheDocument()
  })

  it('renders violation categories from the categories endpoint', () => {
    render(<DashboardPage />)
    expect(screen.getByText('Food & Beverage > Packaged Food')).toBeInTheDocument()
    expect(screen.getByText(/22 violations · 64% compliant/)).toBeInTheDocument()
  })

  it('renders recent inspections as ledger rows with status badges', () => {
    render(<DashboardPage />)
    expect(screen.getByText('Britannia Good Day 200g')).toBeInTheDocument()
    expect(screen.getByText('Amul Butter 500g')).toBeInTheDocument()
    expect(screen.getByText('Patanjali Atta 5kg')).toBeInTheDocument()
    expect(screen.getByText('Compliant')).toBeInTheDocument()
    expect(screen.getByText('Needs review')).toBeInTheDocument()
    expect(screen.getByText('Violation')).toBeInTheDocument()
  })
})