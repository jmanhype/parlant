import { ReactElement, useState } from "react";
import useFetch from "@/hooks/useFetch";
import { Textarea } from "../ui/textarea";
import { Button } from "../ui/button";
import { postData } from "@/utils/api";

interface Props {
    sessionId: string;
}


export default function SessionEvents({sessionId}: Props): ReactElement {
    const [message, setMessage] = useState('');
    const [refetch, setRefetch] = useState(false);
    const {data, error, loading} = useFetch(`sessions/${sessionId}/events`, {kinds: 'message'}, [refetch]);
    
    const postMessage = (content: string) => {
        setMessage('');
        return postData(`sessions/${sessionId}/events`, {kind: 'message', content}).then(() => setRefetch(!refetch));
    }

    return (
        <div className="flex flex-col items-center pt-4 h-full">
            <div className="messages overflow-auto flex-1 flex flex-col">
                {data?.events?.map(event => (
                    <div className={(event.source === 'client' ? 'bg-red-100 self-start' : 'bg-blue-100 self-end') + ' rounded-lg p-2 m-4 mb-1 w-fit'}>{event?.data?.message}</div>
                ))}
            </div>
            <div className="w-full flex items-center gap-4 p-1">
                <Textarea value={message} onChange={(e) => setMessage(e.target.value)} className="resize-none"/>
                <Button onClick={() => postMessage(message)}>Submit</Button>
            </div>
        </div>
    )
}