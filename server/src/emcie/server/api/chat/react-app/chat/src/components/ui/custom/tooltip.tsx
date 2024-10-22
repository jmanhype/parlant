import {
  Tooltip as ShadcnTooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { ReactElement } from 'react';

interface Props {
    children: ReactElement;
    value: string;
    delayDuration?: number;
}

export default function Tooltip({children, value, delayDuration = 0}: Props) {
  return (
    <TooltipProvider>
      <ShadcnTooltip delayDuration={delayDuration}>
        <TooltipTrigger asChild>
            {children}
        </TooltipTrigger>
        <TooltipContent>
          <p>{value}</p>
        </TooltipContent>
      </ShadcnTooltip>
    </TooltipProvider>
  );
}
