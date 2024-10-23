import { ReactElement } from 'react';
import { Check, CheckCheck, CircleAlert, Clock } from 'lucide-react';
import Markdown from 'react-markdown';
import { EventInterface } from '@/utils/interfaces';

interface Props {
    event: EventInterface
}

const statusIcon = {
    pending: <Clock data-testid="pending" height={15} />,
    error: <CircleAlert data-testid="error" height={15} />,
    accepted: <Check data-testid="accepted" height={15} />,
    acknowledged: <CheckCheck data-testid="acknowledged" height={15} />,
    processing: <CheckCheck data-testid="processing" className="text-green-300" height={15} />,
    typing: <CheckCheck data-testid="typing" className="text-green-300" height={15} />,
    ready: <CheckCheck data-testid="ready" className="text-green-300" height={15} />,
};


const formatDateTime = (targetDate: Date | string): string => {
    const date = new Date(targetDate);
    const now = new Date();

    if (now.toDateString() === date.toDateString()) return date.toLocaleTimeString('en-US', {timeStyle: 'short', hour12: false});
    return `${date.toLocaleDateString()} ${date.toLocaleTimeString('en-US', {timeStyle: 'short', hour12: false})}`;
};

export default function Message({event}: Props): ReactElement {
    const isClient = event.source === 'client';
    const serverStatus = event.serverStatus;

    return (
        <div className={(isClient ? 'self-end' : 'self-start') + ' flex m-4 mb-1 gap-[14px]'}>
            {!isClient &&
                <div className='flex items-end'>
                    <img src="parlant-bubble.svg"
                        alt=""
                        height={34}
                        width={36}
                        className='pt-[11px] p-[9px] bg-white rounded-full'/>
                </div>
            }
            <div data-testid="message" className={(isClient ? 'bg-white text-black rounded-br-none' : 'bg-transparent border-[1.3px] border-[#EBECF0] border-solid rounded-bl-none') + ' animate-fade-in rounded-[22px] w-fit max-w-[564px] flex gap-1 items-center relative'}>
                <div style={{wordBreak: 'break-word'}} className="relative font-light text-[16px] pt-[20px] pb-[24px] ps-[34px] pe-[13px]">
                    <Markdown>{event?.data?.message}</Markdown>
                </div>
                <div className='flex h-full font-normal text-[11px] text-[#AEB4BB] pt-[36px] pb-[10px] pe-[14px] font-inter items-end whitespace-nowrap'>
                    <div>{formatDateTime(event.creation_utc)}</div>
                    {isClient && serverStatus && <div className="w-6">{statusIcon[serverStatus]}</div>}
                </div>
            </div>
        </div>
    );
}