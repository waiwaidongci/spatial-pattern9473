import {request} from './client';import {Edge} from '../types/domain';export const getEdges=(id:number)=>request<Edge[]>(`/surveys/${id}/edges`);
