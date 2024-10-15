import { Dispatch, ReactElement, SetStateAction } from "react";
import useFetch from "@/hooks/useFetch";

interface Props {
    agentId: string | undefined;
    setSession: Dispatch<SetStateAction<null>>
}

export default function AgentSessions({agentId, setSession}: Props): ReactElement {
    const results = useFetch('sessions/', {agent_id: agentId});

    return (
        <div className="flex justify-center pt-4">
            {results?.data?.sessions && results.data.sessions.map(session => (
                <div key={session.id} onClick={() => setSession(session.id)} className="bg-slate-200 border border-solid border-black cursor-pointer p-1 rounded">
                    <div>{session.title}</div>
                    <div>{session.end_usser_id}</div>
                </div>
            ))}
        </div>
    )
}