define :juju_port, action: :nothing do
  if params[:action] == :open
    execute "open-port #{params[:name]}" do
      action :run
    end
  elsif params[:action] == :close
    execute "close-port #{params[:name]}" do
      action :run
    end
  end
end