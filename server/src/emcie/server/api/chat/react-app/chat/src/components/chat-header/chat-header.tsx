import { ReactElement } from 'react';
import AgentsSelect from '../agents-select/agents-select';
import { useSession } from '../chatbot/chatbot';
import { SessionInterface } from '@/utils/interfaces';

const newSessionObj: SessionInterface = {end_user_id: '', title: 'New Conversation', agentId: '', creation_utc: new Date().toLocaleString(), id: 'NEW_SESSION'};

export const ChatHeader = (): ReactElement => {
    const {setSessionId, agentId, setNewSession} = useSession();

    const createNewSession = () => {
        setNewSession(newSessionObj);
        setSessionId(newSessionObj.id);
     };

    return (
        <div className='bg-white h-[70px] flex border-b-[0.6px] border-b-solid border-[#EBECF0]'>
            <div role='button' className='text-[16px] text-[#213547] font-medium cursor-pointer lg:w-[308px] flex rounded-[6px] border-[10px] border-solid border-white items-center justify-center hover:bg-gray-100'
                onClick={createNewSession}>
                <img src="parlant-bubble.svg" alt="chat bubble" className='pe-2' />
                New Session
            </div>
            <div className='lg:w-[308px] flex items-center justify-center'>
                <AgentsSelect value={agentId as (string | undefined)} />
            </div>
        </div>
    );
};

export default ChatHeader;