import {atom} from 'jotai';

export const haveLogs = atom(JSON.parse(localStorage.logs || '{}'));
