import {ActionButton} from './action-button'
import type {ActionButtonProps} from './action-button'
import { Slot } from '@radix-ui/react-slot'
import { cva, type VariantProps } from 'class-variance-authority'

const buttonVariants = cva('btn', {
  variants: {
    variant: { default: 'primary', secondary: 'secondary', destructive: 'danger', ghost: 'ghost' },
  },
  defaultVariants: { variant: 'default' },
})

type ButtonProps = ActionButtonProps &
  VariantProps<typeof buttonVariants> & { asChild?: boolean }

export function Button({ asChild = false, variant = 'default', className, type, ...props }: ButtonProps) {
  const classes = buttonVariants({ variant, className })
  if (asChild) {
    return <Slot data-slot="button" data-variant={variant} className={classes} {...props} />
  }
  return <ActionButton data-slot="button" data-variant={variant} className={classes} type={type ?? 'button'} {...props} />
}
