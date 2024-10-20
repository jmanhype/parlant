import { ReactElement, useEffect, useRef, useState } from "react";
import useFetch from "@/hooks/useFetch";
import { Textarea } from "../ui/textarea";
import { Button } from "../ui/button";
import { postData } from "@/utils/api";
import { Skeleton } from "../ui/skeleton";
import { Check, CheckCheck } from "lucide-react";
import Markdown from "react-markdown";
import { groupBy } from "@/utils/obj";

interface Props {
    sessionId: string;
}

interface Event {
    source: 'client' | 'server';
    kind: 'status' | 'message';
    correlation_id: string;
    serverStatus: string | undefined;
    offset: number;
    creation_utc: Date;
    data: {
        status?: string;
        message: string;
    };
}

const emptyPendingMessage: Event = {kind: 'message', source: 'client', creation_utc: new Date(), serverStatus: 'pending', offset: 0, correlation_id: '', data: {message: ''}};

const formatDateTime = (targetDate: Date | string): string => {
    if (typeof targetDate === 'string') targetDate = new Date(targetDate);
    const now = new Date();
    const timeDifference = now.getTime() - targetDate.getTime();
    const oneDayInMilliseconds = 24 * 60 * 60 * 1000;

    if (timeDifference < oneDayInMilliseconds) return targetDate.toLocaleTimeString('en-US', {timeStyle: 'short', hour12: false});
    return `${targetDate.toLocaleDateString()} ${targetDate.toLocaleTimeString('en-US', {timeStyle: 'short', hour12: false})}`;
}

export default function Chat({sessionId}: Props): ReactElement {
    const lastMessageRef = useRef<HTMLDivElement>(null);
    const submitButtonRef = useRef<HTMLButtonElement>(null);
    const textareaRef = useRef<HTMLTextAreaElement>(null);

    const [message, setMessage] = useState('');
    const [pendingMessage, setPendingMessage] = useState<Event>(emptyPendingMessage);
    const [lastOffset, setLastOffset] = useState(0);
    const [messages, setMessages] = useState<Event[]>([]);
    const [isSubmitDisabled, setIsSubmitDisabled] = useState(false);
    const [showSkeleton, setShowSkeleton] = useState(false);
    const {data: lastMessages, setRefetch} = useFetch<{events: Event[]}>(`sessions/${sessionId}/events`, {min_offset: lastOffset, wait: true}, [], true);

    useEffect(() => lastMessageRef?.current?.scrollIntoView(), [messages, pendingMessage]);

    useEffect(() => {
        setMessage('');
        setLastOffset(0);
        setMessages([]);
        setIsSubmitDisabled(false);
        setShowSkeleton(false);
        setRefetch(refetch => !refetch);
        textareaRef?.current?.focus()
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
           if (last?.source === 'client' && correlationsMap?.[last?.correlation_id]) last.serverStatus = correlationsMap?.[last?.correlation_id]?.at(-1)?.data?.status;
           return [...messages, ...withStatusMessages];
        });

        if (lastEvent?.data?.status === 'typing') setShowSkeleton(true);
        else setShowSkeleton(false);

        if (lastEvent?.kind !== 'status' || lastEvent?.data?.status !== 'ready') setRefetch(refetch => !refetch);
        else setIsSubmitDisabled(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [lastMessages])

    const postMessage = (content: string): void => {
        setPendingMessage(pendingMessage => ({...pendingMessage, data: {message: content}}));
        setIsSubmitDisabled(true);
        setMessage('');
        postData(`sessions/${sessionId}/events`, { kind: 'message', content }).then(() => {
            setPendingMessage(pendingMessage => ({...pendingMessage, serverStatus: 'accepted'}));
            setRefetch(refetch => !refetch);
        });
    }

    const onKeyUp = (e: React.KeyboardEvent<HTMLTextAreaElement>): void => {
        if (e.key === 'Enter' && !e.shiftKey) submitButtonRef?.current?.click();
    }

    return (
        <div className="flex flex-col items-center pt-4 h-full">
            <div className="messages overflow-auto flex-1 flex flex-col w-full mb-4" aria-live="polite" role="log" aria-label="Chat messages">
                {(pendingMessage?.data?.message ? [...messages, pendingMessage] : messages).map((event, i) => (
                    <div key={i} ref={lastMessageRef} className={(event.source === 'client' ? 'bg-blue-600 text-white self-start' : 'bg-white self-end') + ' border border-solid border-black rounded-lg p-2 m-4 mb-1 w-fit max-w-[90%] flex gap-1 items-center relative'}>
                        <div className="relative">
                            <Markdown>{event?.data?.message}</Markdown>
                            <div className="text-end text-[unset] opacity-70 text-xs">
                                {formatDateTime(event.creation_utc)}
                            </div>
                        </div>
                        {event.source === 'client' && event.serverStatus &&
                        <div className="w-6 h-full flex">
                            {event.serverStatus === 'accepted' && <Check className="self-end" height={15}/>}
                            {event.serverStatus === 'acknowledged' && <CheckCheck className="self-end" height={15}/>}
                            {{processing: true, typing: true, ready: true}[event.serverStatus] && <CheckCheck className="self-end text-green-300" height={15}/>}
                        </div>
                        }
                    </div>
                ))}
                {showSkeleton && 
                <div ref={lastMessageRef} className="border bg-white border-black self-end rounded-lg p-2 m-4 mb-1 w-[250px]">
                    <Skeleton className="w-[200px] h-[20px] rounded-full bg-gray-400" /> 
                    <Skeleton className="w-[150px] h-[20px] rounded-full bg-gray-400 mt-2" /> 
                </div>}
            </div>
            <div className="w-full flex flex-col lg:flex-row items-center gap-4 p-4 pt-0">
                <Textarea ref={textareaRef} placeholder="What's on your mind?" value={message} onKeyUp={onKeyUp} onChange={(e) => setMessage(e.target.value)} className="resize-none"/>
                <Button variant='ghost' className="border border-solid border-black" ref={submitButtonRef} disabled={isSubmitDisabled ||!message?.trim()} onClick={() => postMessage(message)}>Submit</Button>
            </div>
        </div>
    )
}