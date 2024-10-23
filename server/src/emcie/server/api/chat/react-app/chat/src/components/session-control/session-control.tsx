import { ReactElement } from 'react';
import Sessions from '../sessions/sessions';


export default function SessionControl(): ReactElement {

    return (
        <div className="flex flex-col items-center h-full overflow-auto">
            <Sessions />
        </div>
    );
}