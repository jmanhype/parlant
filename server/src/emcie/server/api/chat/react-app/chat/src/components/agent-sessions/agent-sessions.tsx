import { ReactElement } from "react";
import useFetch from "@/hooks/useFetch";

interface Props {
    agentId: string |undefined;
}

export default function AgentSessions({agentId}: Props): ReactElement {
    const results = useFetch('sessions/', {agent_id: agentId});

    return (
        <div className="flex justify-center pt-4">
            {results?.data?.sessions && results.data.sessions.map(session => (
                <div key={session.id}>
                    <div>{session.title}</div>
                    <div>{session.end_usser_id}</div>
                </div>
            ))}
        </div>
    )
}