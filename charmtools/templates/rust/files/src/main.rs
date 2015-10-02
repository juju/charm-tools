extern crate juju;
use std::env;


/*
	A hook function to be run when the config-changed hook is called by Juju
	After creating this function, add it to the hook registry.
	Next symlink a file in the hooks directory with the corresponding name to
	the binary that cargo build generates.
 */
fn config_changed()->Result<(), String>{
	println!("config changed called");
	return Ok(());
}

fn start()->Result<(), String>{
	println!("start called");
	return Ok(());
}

fn stop()->Result<(), String>{
	println!("stop called");
	return Ok(());
}

fn relation_named_relation_broken()->Result<(), String>{
	println!("relation_named_relation_broken called");
	return Ok(());
}

fn relation_named_relation_changed()->Result<(), String>{
	println!("relation_named_relation_changed called");
	return Ok(());
}

fn relation_named_relation_departed()->Result<(), String>{
	println!("relation_named_relation_departed called");
	return Ok(());
}

fn relation_named_relation_joined()->Result<(), String>{
	println!("relation_named_relation_joined called");
	return Ok(());
}

fn main(){
	let args: Vec<String> = env::args().collect();
	if args.len() > 0{
		//Create our hook register
		let mut hook_registry: Vec<juju::Hook> = Vec::new();

		//Register our hooks with the Juju library
		hook_registry.push(juju::Hook{
			name: "config-changed".to_string(),
			callback: Box::new(config_changed),
		});

		hook_registry.push(juju::Hook{
			name: "start".to_string(),
			callback: Box::new(start),
		});

		hook_registry.push(juju::Hook{
			name: "stop".to_string(),
			callback: Box::new(stop),
		});

		hook_registry.push(juju::Hook{
			name: "relation-named-relation-broken".to_string(),
			callback: Box::new(relation_named_relation_broken),
		});
		hook_registry.push(juju::Hook{
			name: "relation-named-relation-changed".to_string(),
			callback: Box::new(relation_named_relation_changed),
		});
		hook_registry.push(juju::Hook{
			name: "relation-named-relation-departed".to_string(),
			callback: Box::new(relation_named_relation_departed),
		});
		hook_registry.push(juju::Hook{
			name: "relation-named-relation-joined".to_string(),
			callback: Box::new(relation_named_relation_joined),
		});

		//Call the function
		let result =  juju::process_hooks(args, hook_registry);

		if result.is_err(){
				juju::log(&format!("Hook failed with error: {:?}", result.err()));
		}
	}
}
