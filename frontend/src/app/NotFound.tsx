import { Link } from 'react-router'

export function NotFound() {
  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center text-center">
      <h1 className="text-2xl font-semibold">Page not found</h1>
      <Link to="/" className="mt-3 text-sm font-medium text-brand-600">Go home</Link>
    </div>
  )
}
