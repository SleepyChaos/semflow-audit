import type { ComponentProps, ReactNode } from "react"
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { cn } from "@/lib/utils"

type Option = { value: string; label: ReactNode; disabled?: boolean }
type Props = Omit<
  ComponentProps<typeof SelectTrigger>,
  "value" | "onChange" | "children"
> & {
  value: string
  onValueChange: (value: string) => void
  options: Option[]
}

// Radix reserves an empty value for clearing; some workflow options mean "none".
const emptyOption = "__semflow_no_selection__"

export function WorkspaceSelect({
  value,
  onValueChange,
  options,
  className,
  disabled,
  ...props
}: Props) {
  return (
    <Select
      value={value || emptyOption}
      onValueChange={(next) => onValueChange(next === emptyOption ? "" : next)}
      disabled={disabled}
    >
      <SelectTrigger className={cn("workspace-select", className)} {...props}>
        <SelectValue placeholder="请选择" />
      </SelectTrigger>
      <SelectContent
        className="workspace-select-menu"
        align="start"
        sideOffset={2}
      >
        <SelectGroup>
          {options.map((option) => (
            <SelectItem
              key={option.value}
              value={option.value || emptyOption}
              disabled={option.disabled}
            >
              {option.label}
            </SelectItem>
          ))}
        </SelectGroup>
      </SelectContent>
    </Select>
  )
}
