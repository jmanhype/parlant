import { ReactElement } from 'react';
import { Check, CheckCheck, Clock } from 'lucide-react';
import Markdown from 'react-markdown';
import { EventInterface } from '@/utils/interfaces';

interface Props {
    event: EventInterface
}

const statusIcon = {
    // pending: <Clock data-testid="pending" height={15} />,
    pending: <img src='/icons/pending.svg' data-testid="pending" height={11} width={11} className='ms-[4px]'/>,
    error: <img src='/icons/error.svg' data-testid="error" height={11} width={11} className='ms-[4px]'/>,
    accepted: <Check data-testid="accepted" height={15} />,
    // acknowledged: <CheckCheck data-testid="acknowledged" height={15} />,
    acknowledged: <img src='/icons/v.svg' data-testid="acknowledged" height={11} width={11} className='ms-[4px]'/>,
    // processing: <CheckCheck data-testid="processing" className="text-green-300" height={15} />,
    processing: <img src='/icons/green-v.svg' data-testid="processing" height={11} width={11} className='ms-[4px]'/>,
    typing: <img src='/icons/green-v.svg' data-testid="typing" height={11} width={11} className='ms-[4px]'/>,
    ready: <img src='/icons/green-v.svg' data-testid="ready" height={11} width={11} className='ms-[4px]'/>,
    // typing: <CheckCheck data-testid="typing" className="text-green-300" height={15} />,
    // ready: <CheckCheck data-testid="ready" className="text-green-300" height={15} />,
};


const formatDateTime = (targetDate: Date | string): string => {
    const date = new Date(targetDate);

    return date.toLocaleTimeString('en-US', {timeStyle: 'short', hour12: false});
};

export default function Message({event}: Props): ReactElement {
    const isClient = event.source === 'client';
    const serverStatus = event.serverStatus;

    return (
        <div className={(isClient ? 'self-end' : 'self-start') + ' flex my-4 mx-0 mb-1 gap-[14px]'}>
            <div className='w-[206px]'></div>
            <div className='flex-1 flex'>
                {!isClient &&
                    <div className='flex items-end me-[14px]'>
                        <img src="parlant-bubble.svg"
                            alt=""
                            height={34}
                            width={36}
                            className='pt-[11px] p-[9px] bg-white rounded-full'/>
                    </div>
                }
                <div data-testid="message" className={(isClient ? 'bg-white text-black rounded-br-none' : 'bg-transparent border-[1.3px] border-muted border-solid rounded-bl-none') + (isClient && serverStatus === 'error' ? ' !bg-[#FDF2F1]' : '') + ' rounded-[22px] w-fit max-w-[564px] flex gap-1 items-center relative'}>
                    <div style={{wordBreak: 'break-word'}} className="relative font-light text-[16px] pt-[18px] pb-[22px] ps-[32px] pe-[13px]">
                        <Markdown>{event?.data?.message}</Markdown>
                    </div>
                    <div className='flex h-full font-normal text-[11px] text-[#AEB4BB] pt-[36px] pb-[10px] pe-[14px] font-inter items-center whitespace-nowrap'>
                        <div>{formatDateTime(event.creation_utc)}</div>
                        {isClient && serverStatus && <div className="w-6">{statusIcon[serverStatus]}</div>}
                    </div>
                </div>
            </div>
            <div className='w-[206px]'></div>
        </div>
    );
}