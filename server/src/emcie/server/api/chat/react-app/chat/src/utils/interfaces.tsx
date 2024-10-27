export interface AgentInterface {
    id: string;
    name: string;
};

export type ServerStatus = 'pending' | 'error' | 'accepted' | 'acknowledged' | 'processing' | 'typing' | 'ready';

export interface EventInterface {
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
};

export interface SessionInterface {
    id: string;
    title: string;
    end_user_id: string;
    agent_id: string;
    creation_utc: string;
};