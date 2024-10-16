import { ReactElement } from "react";
import useFetch from "@/hooks/useFetch";

interface Props {
    sessionId: string;
}

export default function SessionEvents({sessionId}: Props): ReactElement {
    const {data, error, loading} = useFetch(`sessions/${sessionId}/events`, {kinds: 'message'});

    return (
        <div className="flex flex-col items-center pt-4">
            {data?.events?.map(event => (
                <div className={(event.source === 'client' ? 'bg-red-100 self-start' : 'bg-blue-100 self-end') + ' rounded-lg p-2 m-4 mb-1'}>{event?.data?.message}</div>
            ))}
        </div>
    )
}