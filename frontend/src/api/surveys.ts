import {request} from './client';import {Survey} from '../types/domain';export const getSurveys=()=>request<Survey[]>('/surveys');
