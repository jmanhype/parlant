import { ReactElement, useEffect, useState } from "react";
import useFetch from "@/hooks/useFetch";
import { Textarea } from "../ui/textarea";
import { Button } from "../ui/button";
import { postData } from "@/utils/api";
import { Skeleton } from "../ui/skeleton";

interface Props {
    sessionId: string;
}


export default function SessionEvents({sessionId}: Props): ReactElement {
    const [message, setMessage] = useState('');
    const [refetch, setRefetch] = useState(false);
    const [lastOffset, setLastOffset] = useState(0);
    const [messages, setMessages] = useState([]);
    const [isSubmitDisabled, setIsSubmitDisabled] = useState(false);
    const [showSkeleton, setShowSkeleton] = useState(false);
    // const {data, error, loading} = useFetch(`sessions/${sessionId}/events`);
    const {data: lastMessages, error: lastMessageError, loading: lastMessageLoading} = useFetch(`sessions/${sessionId}/events`, {min_offset: lastOffset, wait: true}, [refetch]);

    useEffect(() => {
        const lastEvent = lastMessages?.events?.at(-1);
        const offset = lastEvent?.offset;
        if (offset) setLastOffset(offset + 1);
        setMessages(messages => [...messages, ...(lastMessages?.events?.filter(e => e.kind === 'message') || [])]);
        if (lastEvent?.kind !== 'status' || lastEvent?.data?.status !== 'ready') setRefetch(!refetch);
        else {
            setShowSkeleton(false);
            setIsSubmitDisabled(false);
        }
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [lastMessages])

    // useEffect(() => {
    //     setLastOffset(data?.events?.length || 0);
    //     setMessages(data?.events?.filter(e => e.kind === 'message') || []);
    // }, [lastMessages])
    
    function postMessage(content: string) {
        setIsSubmitDisabled(true);
        setMessage('');
        setShowSkeleton(true);
        return postData(`sessions/${sessionId}/events`, { kind: 'message', content }).then(() => { setRefetch(!refetch); });
    }
    // {message.class === 'loading' ? 
    //     <div>
    //       <Skeleton className="w-[200px] h-[20px] rounded-full bg-gray-200" /> 
    //       <Skeleton className="w-[150px] h-[20px] rounded-full bg-gray-200 mt-2" /> 
    //     </div> :
    //     <Markdown className='markdown' remarkPlugins={[remarkGfm]}>{message.content}</Markdown>}
    return (
        <div className="flex flex-col items-center pt-4 h-full">
            <div className="messages overflow-auto flex-1 flex flex-col w-full">
                {messages.map((event, i) => (
                    <div key={i} className={(event.source === 'client' ? 'bg-red-100 self-start' : 'bg-blue-100 self-end') + ' rounded-lg p-2 m-4 mb-1 w-fit'}>{event?.data?.message}</div>
                ))}
                {showSkeleton && 
                <div className="bg-blue-100 self-end rounded-lg p-2 m-4 mb-1 w-[250px]">
                    <Skeleton className="w-[200px] h-[20px] rounded-full bg-gray-200" /> 
                    <Skeleton className="w-[150px] h-[20px] rounded-full bg-gray-200 mt-2" /> 
                </div>}
            </div>
            <div className="w-full flex items-center gap-4 p-1">
                <Textarea value={message} onChange={(e) => setMessage(e.target.value)} className="resize-none"/>
                <Button disabled={isSubmitDisabled ||!message?.trim()} onClick={() => postMessage(message)}>Submit</Button>
            </div>
        </div>
    )
}