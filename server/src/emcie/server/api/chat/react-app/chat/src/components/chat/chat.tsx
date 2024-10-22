import { ReactElement, useEffect, useRef, useState } from 'react';
import useFetch from '@/hooks/useFetch';
import { Textarea } from '../ui/textarea';
import { Button } from '../ui/button';
import { postData } from '@/utils/api';
import { Skeleton } from '../ui/skeleton';
import { groupBy } from '@/utils/obj';
import Message from '../message/message';
import { useSession } from '../chatbot/chatbot';

export type ServerStatus = 'pending' | 'error' | 'accepted' | 'acknowledged' | 'processing' | 'typing' | 'ready';

export interface Event {
    source: 'client' | 'server';
    kind: 'status' | 'message';
    correlation_id: string;
    serverStatus: ServerStatus;
    offset: number;
    creation_utc: Date;
    data: {
        status?: ServerStatus;
        message: string;
    };
}

const emptyPendingMessage: Event = {
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
    const [pendingMessage, setPendingMessage] = useState<Event>(emptyPendingMessage);
    const [lastOffset, setLastOffset] = useState(0);
    const [messages, setMessages] = useState<Event[]>([]);
    const [isSubmitDisabled, setIsSubmitDisabled] = useState(false);
    const [showSkeleton, setShowSkeleton] = useState(false);
    const {data: lastMessages, refetch} = useFetch<{events: Event[]}>(`sessions/${sessionId}/events`, {min_offset: lastOffset, wait: true}, [], true);

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
        const correlationsMap = groupBy(lastMessages?.events || [], (item: Event) => item?.correlation_id.split('.')[0]);
        const newMessages = lastMessages?.events?.filter(e => e.kind === 'message') || [];
        const withStatusMessages = newMessages.map(newMessage => ({...newMessage, serverStatus: correlationsMap?.[newMessage.correlation_id.split('.')[0]]?.at(-1)?.data?.status}));
        setMessages(messages => {
            const last = messages.at(-1);
           if (last?.source === 'client' && correlationsMap?.[last?.correlation_id]) last.serverStatus = correlationsMap[last.correlation_id].at(-1)?.data?.status || last.serverStatus;
           return [...messages, ...withStatusMessages] as Event[];
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
        <div className="flex flex-col items-center pt-4 h-full">
            <div className="messages overflow-auto flex-1 flex flex-col w-full mb-4" aria-live="polite" role="log" aria-label="Chat messages">
                {(pendingMessage?.data?.message ? [...messages, pendingMessage] : messages).map((event, i) => (
                    <div key={i} ref={lastMessageRef} className="flex flex-col">
                        <Message event={event}/>
                    </div>
                ))}
                {showSkeleton && 
                <div ref={lastMessageRef} className="border bg-white border-black self-end rounded-lg p-2 m-4 mb-1 w-[250px]">
                    <Skeleton className="w-[200px] h-[20px] rounded-full bg-gray-400" /> 
                    <Skeleton className="w-[150px] h-[20px] rounded-full bg-gray-400 mt-2" /> 
                </div>}
            </div>
            <div className="w-full flex flex-col lg:flex-row items-center gap-4 p-4 pt-0">
                <Textarea role="textbox" ref={textareaRef} placeholder="What's on your mind?" value={message} onKeyUp={onKeyUp} onChange={(e) => setMessage(e.target.value)} className="resize-none"/>
                <Button variant='ghost' className="border border-solid border-black" ref={submitButtonRef} disabled={isSubmitDisabled ||!message?.trim()} onClick={() => postMessage(message)}>Submit</Button>
            </div>
        </div>
    );
}