import { ReactElement } from 'react';
import { Check } from 'lucide-react';
import Markdown from 'react-markdown';
import { EventInterface } from '@/utils/interfaces';
import { getTimeStr } from '@/utils/date';
import styles from './message.module.scss';
import { Spacer } from '../ui/custom/spacer';

interface Props {
    event: EventInterface
}

const statusIcon = {
    pending: <video src='/mp4/loading.mp4' autoPlay loop data-testid="pending" height={12.2} width={12.2} className={'clip- ms-[4px] rounded-full ' + styles.pendingVideo}/>,
    error: <img src='/icons/error.svg' data-testid="error" height={11} width={11} className='ms-[4px]'/>,
    accepted: <Check data-testid="accepted" height={15} />,
    acknowledged: <img src='/icons/v.svg' data-testid="acknowledged" height={11} width={11} className='ms-[4px]'/>,
    processing: <img src='/icons/green-v.svg' data-testid="processing" height={11} width={11} className='ms-[4px]'/>,
    typing: <img src='/icons/green-v.svg' data-testid="typing" height={11} width={11} className='ms-[4px]'/>,
    ready: <img src='/icons/green-v.svg' data-testid="ready" height={11} width={11} className='ms-[4px]'/>,
};

export default function Message({event}: Props): ReactElement {
    const isClient = event.source === 'client';
    const serverStatus = event.serverStatus;

    return (
        <div className='flex my-4 mx-0 mb-1 w-full justify-between'>
            <Spacer/>
            <div className={(isClient ? 'justify-end' : 'justify-start') + ' flex-1 flex max-w-[1200px] items-end'}>
                {!isClient &&
                    <div className='flex items-end me-[14px]'>
                        <img src="parlant-bubble.svg" alt="Parlant"/>
                    </div>
                }
                <div data-testid="message" className={(isClient ? 'bg-white text-black rounded-br-none' : 'bg-transparent border-[1.3px] border-muted border-solid rounded-bl-none') + (isClient && serverStatus === 'error' ? ' !bg-[#FDF2F1]' : '') + ' rounded-[22px] w-fit max-w-[564px] flex gap-1 items-center relative'}>
                    <div style={{wordBreak: 'break-word'}} className="relative font-light text-[16px] pt-[18px] pb-[22px] ps-[32px] pe-[13px]">
                        <Markdown>{event?.data?.message}</Markdown>
                    </div>
                    <div className='flex h-full font-normal text-[11px] text-[#AEB4BB] pt-[36px] pb-[10px] pe-[14px] font-inter self-end items-end whitespace-nowrap'>
                        <div className='flex items-center'>
                            <div>{getTimeStr(event.creation_utc)}</div>
                            {isClient && serverStatus && <div className="w-6">{statusIcon[serverStatus]}</div>}
                        </div>
                    </div>
                </div>
            </div>
            <Spacer/>
        </div>
    );
}