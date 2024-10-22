import { ReactElement, useEffect, useRef, useState } from 'react';
import useFetch from '@/hooks/useFetch';
import { Textarea } from '../ui/textarea';
import { Button } from '../ui/button';
import { postData } from '@/utils/api';
import { Skeleton } from '../ui/skeleton';
import { groupBy } from '@/utils/obj';
import Message from '../message/message';
import { useSession } from '../chatbot/chatbot';
import { EventInterface } from '@/utils/interfaces';

const emptyPendingMessage: EventInterface = {
    kind: 'message',
    source: 'client',
    creation_utc: new Date(),
    serverStatus: 'pending',
    offset: 0,
    correlation_id: '',
    data: {
        message: ''
    }
};

export default function Chat(): ReactElement {
    const lastMessageRef = useRef<HTMLDivElement>(null);
    const submitButtonRef = useRef<HTMLButtonElement>(null);
    const textareaRef = useRef<HTMLTextAreaElement>(null);
    const {sessionId} = useSession();

    const [message, setMessage] = useState('');
    const [pendingMessage, setPendingMessage] = useState<EventInterface>(emptyPendingMessage);
    const [lastOffset, setLastOffset] = useState(0);
    const [messages, setMessages] = useState<EventInterface[]>([]);
    const [isSubmitDisabled, setIsSubmitDisabled] = useState(false);
    const [showSkeleton, setShowSkeleton] = useState(false);
    const {data: lastMessages, refetch} = useFetch<{events: EventInterface[]}>(`sessions/${sessionId}/events`, {min_offset: lastOffset, wait: true}, [], true);

    const resetChat = () => {
        setMessage('');
        setLastOffset(0);
        setMessages([]);
        setIsSubmitDisabled(false);
        setShowSkeleton(false);
    };

    useEffect(() => lastMessageRef?.current?.scrollIntoView?.(), [messages, pendingMessage]);

    useEffect(() => {
        resetChat();
        refetch();
        textareaRef?.current?.focus();
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [sessionId]);

    useEffect(() => {
        const lastEvent = lastMessages?.events?.at(-1);
        if (!lastEvent) return;
        if (pendingMessage.data.message) setPendingMessage(emptyPendingMessage);
        const offset = lastEvent?.offset;
        if (offset) setLastOffset(offset + 1);
        const correlationsMap = groupBy(lastMessages?.events || [], (item: EventInterface) => item?.correlation_id.split('.')[0]);
        const newMessages = lastMessages?.events?.filter(e => e.kind === 'message') || [];
        const withStatusMessages = newMessages.map(newMessage => ({...newMessage, serverStatus: correlationsMap?.[newMessage.correlation_id.split('.')[0]]?.at(-1)?.data?.status}));
        setMessages(messages => {
            const last = messages.at(-1);
           if (last?.source === 'client' && correlationsMap?.[last?.correlation_id]) last.serverStatus = correlationsMap[last.correlation_id].at(-1)?.data?.status || last.serverStatus;
           return [...messages, ...withStatusMessages] as EventInterface[];
        });

        const lastEventStatus = lastEvent?.data?.status;

        if (lastEventStatus === 'typing') setShowSkeleton(true);
        else setShowSkeleton(false);

        refetch();
    
        if (lastEvent?.kind === 'status' && (lastEventStatus === 'ready' || lastEventStatus === 'error')) {
            setIsSubmitDisabled(false);
        }
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [lastMessages]);

    const postMessage = (content: string): void => {
        setPendingMessage(pendingMessage => ({...pendingMessage, data: {message: content}}));
        setIsSubmitDisabled(true);
        setMessage('');
        postData(`sessions/${sessionId}/events`, { kind: 'message', content }).then(() => {
            setPendingMessage(pendingMessage => ({...pendingMessage, serverStatus: 'accepted'}));
            refetch();
        });
    };

    const onKeyUp = (e: React.KeyboardEvent<HTMLTextAreaElement>): void => {
        if (e.key === 'Enter' && !e.shiftKey) submitButtonRef?.current?.click();
    };

    return (
        <div className="flex flex-col items-center h-full max-w-[1200px] m-auto">
            <div className="messages overflow-auto flex-1 flex flex-col w-full mb-4" aria-live="polite" role="log" aria-label="Chat messages">
                {(pendingMessage?.data?.message ? [...messages, pendingMessage] : messages).map((event, i) => (
                    <div key={i} ref={lastMessageRef} className="flex flex-col">
                        <Message event={event}/>
                    </div>
                ))}
                {showSkeleton && 
                <div className='flex m-4 mb-1 gap-[14px]'>
                    <div className='flex items-end'>
                        <img src="parlant-bubble.svg" alt="" className='pt-[11px] p-[9px] bg-white rounded-full'/>
                    </div>
                    <div ref={lastMessageRef} className="bg-transparent border-[1.3px] border-[#EBECF0] border-solid rounded-bl-none self-start  rounded-[22px] p-2 m-4 mb-1 w-[250px]">
                        <Skeleton className="w-[200px] h-[20px] rounded-full bg-gray-400" /> 
                        <Skeleton className="w-[150px] h-[20px] rounded-full bg-gray-400 mt-2" /> 
                    </div>
                </div>}
            </div>
            <div className="w-full border border-[#EBECF0] border-solid rounded-full flex flex-row justify-center items-center bg-white p-[0.9rem] ps-[24px] pe-0 h-[48.67px] max-w-[1200px] relative mb-[26px]">
                <img src="/icons/edit.svg" alt="" className="me-[8px] h-[14px] w-[14px]"/>
                <Textarea role="textbox"
                    ref={textareaRef}
                    placeholder="Message..."
                    value={message}
                    onKeyUp={onKeyUp}
                    onChange={(e) => setMessage(e.target.value)}
                    style={{boxShadow: 'none'}}
                    rows={1}
                    className="resize-none border-none h-full rounded-none min-h-[unset] p-0 whitespace-nowrap no-scrollbar"/>
                <Button variant='ghost'
                    className="max-w-[60px] rounded-full hover:bg-white"
                    ref={submitButtonRef}
                    disabled={isSubmitDisabled ||!message?.trim()}
                    onClick={() => postMessage(message)}>
                    <img src="/icons/send.svg" alt="" />
                </Button>
            </div>
        </div>
    );
}