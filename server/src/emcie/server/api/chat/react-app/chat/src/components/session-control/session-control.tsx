import { ReactElement, useState } from 'react';
import AgentsSelect from '../agents-select/agents-select';
import Sessions from '../sessions/sessions';
import { Button } from '../ui/button';
import { postData } from '@/utils/api';
import Tooltip from '../ui/custom/tooltip';
import { Plus } from 'lucide-react';
import { useSession } from '../chatbot/chatbot';


export default function SessionControl(): ReactElement {
    const [selectedAgent, setSelectedAgent] = useState<string>();
    const {setSessionId} = useSession();

    const createNewSession = () => {
       return postData('sessions?allow_greeting=true', {end_user_id: '1122', agent_id: selectedAgent, title: 'New Conversation' })
        .then(res => {
            setSessionId(res.session.id);
        });
    };

    return (
        <div className="flex flex-col items-center h-full overflow-auto">
            <div className="flex justify-between gap-4 w-full pl-4 pr-4 lg:w-[80%] lg:pl-0 lg:pr-0 pt-4 pb-4 sticky top-0 bg-[#e2e8f0]">
                <AgentsSelect value={selectedAgent} setSelectedAgent={val => {setSelectedAgent(val); setSessionId(null);}}/>
                <Tooltip value="Add a new session">
                    <Button variant='ghost' className="border border-black border-solid h-[40px] w-[40px] p-0" disabled={!selectedAgent} onClick={() => createNewSession()}>
                        <Plus/>
                    </Button>
                </Tooltip>
            </div>
            {selectedAgent && <Sessions agentId={selectedAgent} />}
        </div>
    );
}