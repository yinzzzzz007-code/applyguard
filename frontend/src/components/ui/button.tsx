import type { ComponentProps } from 'react'
import { Slot } from '@radix-ui/react-slot'
import { cva, type VariantProps } from 'class-variance-authority'

const buttonVariants = cva('btn', {
  variants: {
    variant: { default: 'primary', secondary: 'secondary', destructive: 'danger', ghost: 'ghost' },
  },
  defaultVariants: { variant: 'default' },
})

type ButtonProps = ComponentProps<'button'> &
  VariantProps<typeof buttonVariants> & { asChild?: boolean }

export function Button({ asChild = false, variant = 'default', className, type, ...props }: ButtonProps) {
  const classes = buttonVariants({ variant, className })
  if (asChild) {
    return <Slot data-slot="button" data-variant={variant} className={classes} {...props} />
  }
  return <button data-slot="button" data-variant={variant} className={classes} type={type ?? 'button'} {...props} />
}
