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
    side?: 'bottom' | 'top' | 'right' | 'left';
}

export default function Tooltip({children, value, side = 'bottom', delayDuration = 0}: Props) {
  return (
    <TooltipProvider>
      <ShadcnTooltip delayDuration={delayDuration}>
        <TooltipTrigger asChild>
            {children}
        </TooltipTrigger>
        <TooltipContent side={side} style={{boxShadow: 'none'}} className='left-[34px] h-[32px] text-[13px] font-normal font-inter rounded-[20px] border border-[#EBECF0] border-solid bg-white p-[5px_16px_7px_16px]'>
          <p>{value}</p>
        </TooltipContent>
      </ShadcnTooltip>
    </TooltipProvider>
  );
}
