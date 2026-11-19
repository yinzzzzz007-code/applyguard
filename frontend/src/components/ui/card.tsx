import type { ComponentProps } from 'react'
import { Slot } from '@radix-ui/react-slot'

type CardPartProps = ComponentProps<'div'> & { asChild?: boolean }

export function Card({ asChild = false, ...props }: CardPartProps) {
  const Root = asChild ? Slot : 'div'
  return <Root data-slot="card" {...props} />
}

export function CardHeader({ asChild = false, ...props }: CardPartProps) {
  const Root = asChild ? Slot : 'div'
  return <Root data-slot="card-header" {...props} />
}

export function CardTitle({ asChild = false, ...props }: CardPartProps) {
  const Root = asChild ? Slot : 'div'
  return <Root data-slot="card-title" {...props} />
}

export function CardDescription({ asChild = false, ...props }: CardPartProps) {
  const Root = asChild ? Slot : 'div'
  return <Root data-slot="card-description" {...props} />
}
