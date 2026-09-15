from reverend.workstation.presentation import response_details


def test_response_details_exposes_safe_runtime_summary():
    metadata={
        'role':'deep_reason','model':'deepseek-r1:8b',
        'completion_reason':'complete','generated_tokens':321,'prompt_tokens':1200,
        'hidden_reasoning_present':True,'thinking_activity_count':4,
        'requested_output_tokens':4096,'context':8192,
        'residency_policy':'exclusive','residency_unload_count':2,
        'task_id':'task-1','task_state':'active','requirement_count':3,
        'acceptance_criteria_count':1,'high_assurance':True,
        'verification':{'outcome':'pass','checked_count':2,'passed_count':2,
                        'failed_count':0,'unchecked_count':2,'repair_attempted':False},
        'agent_loop':{'auto_continuations':1,'stop_reason':'natural_completion',
                      'iterations':[{'iteration':1}]},
        'checkpoint':{'available':False,'continuation_count':1},
        'sources':[{'content':'SECRET SOURCE BODY'}],
        'evidence':{'outcome':'sufficient'},
        'citation':{'status':'present','complete':True},
        'model_calls':2,'total_elapsed_seconds':4.2,
        'prompt':'SECRET PROMPT','raw_response':'SECRET RAW','thinking':'SECRET THINKING',
    }
    result=response_details(metadata)
    assert result['model']['role']=='deep_reason'
    assert result['completion']['hidden_reasoning_used'] is True
    assert result['verification']['outcome']=='pass'
    assert result['continuation']['auto_continuations']==1
    assert result['evidence']['source_count']==1
    assert result['performance']['model_calls']==2
    serialized=str(result)
    assert 'SECRET PROMPT' not in serialized
    assert 'SECRET RAW' not in serialized
    assert 'SECRET THINKING' not in serialized
    assert 'SECRET SOURCE BODY' not in serialized


def test_response_details_preserves_false_and_zero():
    result=response_details({'completion_reason':'complete','incomplete':False,
        'continuation_eligible':False,'answer_started':True,'generated_tokens':0,
        'model_calls':0,'sources':[]})
    assert result['completion']['incomplete'] is False
    assert result['completion']['generated_tokens']==0
    assert result['performance']['model_calls']==0


def test_response_details_surfaces_typed_error_only():
    result=response_details({'error_code':'verification_failed',
        'error':'Verifier rejected answer.','chain_of_thought':'private'})
    assert result['error']=={'code':'verification_failed','message':'Verifier rejected answer.'}
    assert 'private' not in str(result)
