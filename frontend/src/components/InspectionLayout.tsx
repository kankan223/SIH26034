import { Outlet } from 'react-router-dom'
import { MeasureRule } from '../components/MeasureRule'

export function InspectionLayout() {
  return (
    <div className="flex min-h-screen bg-paper">
      <MeasureRule tickCount={4} />
      <main className="ml-20 p-6 max-w-4xl w-full">
        <Outlet />
      </main>
    </div>
  )
}
